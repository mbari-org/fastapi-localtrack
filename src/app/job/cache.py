import pickledb
from datetime import datetime as dt, datetime
from pathlib import Path
from typing import List

from deepsea_ai.logger.job_cache import job_hash
from pydantic import ValidationError

from app import __version__
import app.logger as logger
from app.job import JobEntry
from app.job.model import JobStatus, MediaIndex, JobIndex
from app.logger import info, err, warn


class JobCache:

    def __init__(self, output_path: Path):
        """
        Initialize the cache with the account we are running in
        """
        account = 'LOCAL'

        # create the output path if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)

        info(f"Initializing job cache in {output_path}")

        db_file = output_path / f'job_cache_{account}.db'
        if not db_file.exists():
            info(f"Creating job cache database in {output_path}")
            self.db = pickledb.PickleDB(location=db_file.as_posix(), auto_dump=True, sig=True)
        else:
            info(f"Using existing job cache database in {output_path}")
            self.db = pickledb.load(db_file.as_posix(), True)

    def create_report(self, job_name: str, output_path: Path) -> Path:
        """
        Create a report of the jobs that were run
        :param job_name: Name of the job
        :param output_path: Path to write the report to
        :return: Path to the report
        """
        # create the output path if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)

        # create a file name that replaces spaces with underscores and adds a timestamp
        job_report_name = f"{job_name.replace(' ', '_')}_{dt.utcnow().strftime('%Y%m%d')}.txt"
        output_path = output_path / job_report_name
        info(f"JobCache: Creating job report for {job_name} in {output_path}")

        # fetch the job id if available
        job_uuid = job_hash(job_name)
        if not self.db.get(job_uuid):
            warn(f"Unable to find job {job_name} in cache")
            return

        created_time = self.db.get(job_uuid)[JobIndex.CREATED_TIME]
        last_update = self.db.get(job_uuid)[JobIndex.UPDATE_TIME]
        num_media = len(self.get_all_media_names(job_name))
        job_report_name = f"{job_name}, Total media: {num_media}, Created at: {created_time}, Last update: {last_update} "

        with open(output_path.as_posix(), 'w') as f:
            f.write(f"fastapi-accutrack {__version__}\n")
            f.write(f"Job: {job_report_name}\n")
            f.write(f"==============================================================================================\n")
            f.write(f"Index, Media, Last Updated, Status\n")

            # Write the status of each media file in the job
            media_names = self.get_all_media_names(job_name)
            for idx, media_name in enumerate(sorted(media_names)):
                media = self.get_media(media_name, job_name)
                f.write(f"{idx}, {media_name}, {media[MediaIndex.UPDATE_TIME]}, {media[MediaIndex.STATUS]}\n")

        # Return the path to the report
        return output_path

    def get_all_media_names(self, job_name: str) -> List[str]:
        """
        Get all the media file names associated with a job
        """
        job_uuid = job_hash(job_name)
        return [self.db.get(key)[JobIndex.NAME] for key in self.db.getall() if
                self.db.get(key)[MediaIndex.UUID] == job_uuid]

    def set_media(self, job_name: str, media_file: str, status: str, update_dt: str = None):
        """
        Add a video file to the cache, updating the status of the media if it already exists
        :param job_name: The name of the job
        :param media_file: The video file
        :param update_dt: The date and time the video file was updated
        :param status: The status of the job
        """
        job_uuid = job_hash(job_name)
        media_uuid = job_hash(media_file + job_name)
        if update_dt is None:
            update_dt = dt.utcnow().strftime("%Y%m%dT%H%M%S")
        else:
            update_dt = datetime.strptime(update_dt, "%Y%m%dT%H%M%S").strftime("%Y%m%dT%H%M%S")
        if status == JobStatus.FAILED or status == JobStatus.UNKNOWN:
            err(f"Updating video file {media_file} to job {job_name} in cache with status {status}")
        else:
            info(f"Updating video file {media_file} to job {job_name} in cache with status {status}")

        self.db.set(media_uuid, [media_file, job_uuid, update_dt, status])

    def set_job(self, job: JobEntry):
        """
        Add a job in the cache. A job is uniquely identified by the job name
        :param job: The job entry to add to the cache
        """
        job_uuid = job_hash(job.name)
        j = self.db.get(job_uuid)
        if j:
            # get the video files and add the new video files if they are not already in the list
            media = j[JobIndex.MEDIA]
            for v in media:
                if v not in job.media:
                    job.media.append(v)
                    info(f"JobCache: Added video file {v} to job {job.name} running on {job.cluster}")

        # update the job
        if job.status == JobStatus.FAILED:
            err(f"Updating job {job.name} running on {job.cluster} in cache status to {job.status}")
        else:
            info(f"Updating job {job.name} running on {job.cluster} in cache status to {job.status}")
        job_existing = self.db.get(job_uuid)
        updated_timestamp = dt.utcnow().strftime("%Y%m%dT%H%M%S")
        if job_existing:  # if the job exists, keep the created timestamp
            created_timestamp = job_existing[JobIndex.CREATED_TIME]
        else:
            created_timestamp = dt.utcnow().strftime("%Y%m%dT%H%M%S")

        self.db.set(job_uuid, [job.name,
                               job.cluster,
                               job.model,
                               job.media,
                               created_timestamp,
                               updated_timestamp,
                               job.status,
                               job.email,
                               job.model])

        info(f"Added job {job.name} running on {job.cluster} to cache")

    def get_job_by_name(self, job_name: str) -> List[JobEntry]:
        """
        Get a job from the cache. A job is uniquely identified by the hash of the job name
        """
        job_uuid = job_hash(job_name)
        return self.db.get(job_uuid)

    def get_job_by_uuid(self, job_uuid: str) -> List[JobEntry]:
        """
        Get a job from the cache by its uuid
        """
        return self.db.get(job_uuid)

    def get_media(self, media_name: str, job_name: str) -> List[JobEntry]:
        """
        Get a media from the cache. A media is uniquely identified by the hash of the media name
        :param media_name: The name of the media file
        :param job_name: The name of the job
        :return: The list of media file information
        """
        media_uuid = job_hash(media_name + job_name)
        return self.db.get(media_uuid)

    def get_num_completed(self, job_name: str) -> int:
        """
        Get the number of completed media files in a job
        :param job_name: The name of the job
        """
        job_uuid = job_hash(job_name)
        completed = 0
        for video_uuid in self.db.getall():
            if self.db.get(video_uuid)[MediaIndex.UUID] == job_uuid:
                if self.db.get(video_uuid)[MediaIndex.STATUS] == JobStatus.SUCCESS:
                    completed += 1
        return completed

    def get_num_failed(self, job_name: str) -> int:
        """
        Get the number of failed media files in a job
        :param job_name: The name of the job
        """
        job_uuid = job_hash(job_name)
        failed = 0
        for video_uuid in self.db.getall():
            if self.db.get(video_uuid)[MediaIndex.UUID] == job_uuid:
                if self.db.get(video_uuid)[MediaIndex.STATUS] == JobStatus.FAILED:
                    failed += 1
        return failed

    def remove_job_by_uuid(self, job_uuid: str):
        """
        Remove a job from the cache by its uuid
        """
        self.db.rem(job_uuid)

        # get all the video files associated with the job and remove them from the cache
        to_remove = []
        for video_uuid in self.db.getall():
            if self.db.get(video_uuid)[MediaIndex.UUID] == job_uuid:
                to_remove.append(video_uuid)

        for video_uuid in to_remove:
            self.db.rem(video_uuid)
        info(f"JobCache: Removed job {job_uuid} from cache")

    def remove_job_by_name(self, job_name: str):
        """
        Remove a job from the cache. A job is uniquely identified by the hash of the job name
        """
        job_uuid = job_hash(job_name)
        self.remove_job_by_uuid(job_uuid)
        info(f"JobCache: Removed job {job_name} from cache")

    def get_all(self) -> List[List[JobEntry]]:
        """
        Get all jobs from the cache
        """
        return self.db.getall()

    def clear(self):
        """
        Clear the cache
        """
        self.db.deldb()
        self.db.dump()
        info("Cleared cache")

    def update_status(self, job_uuid: str, status: str):
        # update the status of the job
        job = self.db.get(job_uuid)
        if job:
            job[JobIndex.STATUS] = status
            self.db.set(job_uuid, job)
            info(f"JobCache: Updated job {job_uuid} status to {status}")


if __name__ == '__main__':
    logger.create_logger_file(Path.cwd(), "test")
    jc = JobCache(Path.cwd())
    name = "Dive 1377 with megadetector"
    try:
        data = {
            "name": name,
            "cluster": "LOCAL",
            "model": "megadetector",
            "media": ["vid1.mp4", "vid2.mp4", "vid3.mp4"],
            "created_time": datetime.utcnow(),
            "update_time": datetime.utcnow(),
            "status": JobStatus.RUNNING,
            "email": "",
            "runner_id": ""
        }
        job = JobEntry(**data)
        jc.set_job(job)
        info(f'Getting job {name} {jc.get_job_by_name(name)}')

    # add more videos to the job

        data = {
            "name": name,
            "cluster": "LOCAL",
            "model": "megadetector",
            "media": ["vid4.mp4", "vid5.mp4", "vid6.mp4"],
            "created_time": datetime.utcnow(),
            "update_time": datetime.utcnow(),
            "status": JobStatus.RUNNING,
            "email": "",
            "runner_id": ""
        }
        jc.set_job(JobEntry(**data))
        info(f'Getting job {name} {jc.get_job_by_name(name)}')

        # update the status of the video to RUNNING
        for status in [JobStatus.RUNNING, JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.QUEUED, JobStatus.UNKNOWN]:
            jc.set_media(name, "vid1.mp4", status)
            info(f"Getting media {jc.get_media('vid1.mp4', name)}")

        for v in ['vid1.mp4', 'vid2.mp4', 'vid3.mp4', 'vid4.mp4']:
            jc.set_media(name, v, JobStatus.SUCCESS)
            info(f"Getting media {jc.get_media(v, name)}")

        # Set the last one to failed
        jc.set_media(name, 'vid5.mp4', JobStatus.FAILED)

        # Four should be completed
        info(f"Num completed {name} {jc.get_num_completed(name)}")

        # get all media files for the job
        medias = jc.get_all_media_names(name)
        info(f"Media files for job {name}: {medias}")

        # get the status of each media file
        for m in medias:
            info(f"Status of {m}: {jc.get_media(m, name)}")  # should be SUCCESS except for vid5.mp4

        # create a report for the job that has all the media files and their status
        jc.create_report(name, Path.cwd())

        # clean-up
        jc.remove_job_by_name(name)

    except ValidationError as e:
        err(e.json())