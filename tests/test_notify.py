# fastapi-accutrack, Apache-2.0 license
# Filename: tests/test_notify.py
# Description: Test fake notify endpoint
import json
from pathlib import Path

import requests


def setup_notifier():
    """
    Setup the notifier
    :return:
    """
    from fastapi import FastAPI, UploadFile, Form

    app = FastAPI()

    @app.post("/notify")
    async def receive_notify(
            metadata: str = Form(...),
            file: UploadFile = Form(...)
    ):
        # Process the message parts as needed
        if metadata and file:
            # Do something with the message parts
            print(f"Received message part 1: {metadata}")

            # Read the contents of file as bytes or perform other operations
            file_contents = await file.read()
            print(f"Received message part 2: {file.filename} ({len(file_contents)} bytes)")

            return {"message": "Message received and processed."}
        else:
            return {"error": "Invalid message format."}


    if __name__ == '__main__':
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=8000)
def test_multipart_notify():
    """
    Test that the multipart notify sends the correct data
    :return:
    """
    # Create a test file
    test_file = Path(__file__).parent / 'test_file.txt'
    with test_file.open('w+') as f:
        f.write('test')

    # Create the multipart form data
    files = {'file': ('test_file.txt', test_file.open('rb'), 'text/plain')}
    data = {'metadata': json.dumps({'test': 'test'})}

    # Send the request
    response = requests.post('http://localhost:8000/notify', files=files, data=data)

    # Check the response
    assert response.status_code == 200
    assert response.json() == {"message": "Message received and processed."}

