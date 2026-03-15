import asyncio
import json
import websockets

async def test_websocket():
    uri = "ws://127.0.0.1:8000/ws?token=dev-token"

    async with websockets.connect(uri) as ws:
        # Step 1: Receive connection ack
        print("Waiting for connection ack...")
        ack = await ws.recv()
        print(f"✓ Received ACK: {ack}")

        # Step 2: Send a text message
        text_msg = json.dumps({"type": "text", "text": "What is Python?"})
        print(f"\n→ Sending: {text_msg}")
        await ws.send(text_msg)

        # Step 3: Receive bot response
        print("\nWaiting for bot response...")
        response = await ws.recv()
        print(f"✓ Received: {response}")

        # Step 4: End the session
        end_msg = json.dumps({"type": "end"})
        print(f"\n→ Sending: {end_msg}")
        await ws.send(end_msg)

        # Step 5: Receive close ack
        close_ack = await ws.recv()
        print(f"✓ Received: {close_ack}")

# Run the test
asyncio.run(test_websocket())
