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

    uvicorn.run(app, host="0.0.0.0", port=6000)
