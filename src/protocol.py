import json


def parse_http_path(request_text):
    lines = request_text.splitlines()
    if not lines:
        return None

    first_line = lines[0].strip()
    parts = first_line.split()

    if len(parts) < 2:
        return None

    method = parts[0]
    path = parts[1]
    return method, path


def http_response(status_code, body, content_type="application/json"):
    status_messages = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found"
    }
    status_text = status_messages.get(status_code, "OK")

    if isinstance(body, dict):
        body = json.dumps(body)

    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
        f"{body}"
    )
    return response.encode()


def format_board_state(state):
    return json.dumps({
        "type": "BOARD",
        "data": state
    })


def format_message(msg_type, content):
    return json.dumps({
        "type": msg_type,
        "data": content
    })
