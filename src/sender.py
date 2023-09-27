import requests

# URL of the FastAPI endpoint to send the notification
api_url = "http://localhost:8000/notify"

# Notification data
notification_type = "example_notification"

# Open and read the contents of the file
with open("/Users/dcline/Dropbox/code/fastapi-accutrack/src/app/runner/tmp/1/output/V4361_20211006T163856Z_h265_1sec.tracks.tar.gz", "rb") as file:
    notification_message = file.read()

# Create a dictionary with the data to send
data = {
    "metadata": notification_type,
}

# Create a dictionary with the file to send
files = {
    "file": notification_message,
}

# Send the multi-part POST request
response = requests.post(api_url, data=data, files=files)

# Check the response
if response.status_code == 200:
    print("Notification sent successfully")
else:
    print(f"Failed to send notification. Status code: {response.status_code}")
    print(response.text)
