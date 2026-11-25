import logging

import httpx

# HTTP library logs can include URLs with Telegram's bot credential.
for name in ("httpx", "httpcore"):
    logging.getLogger(name).setLevel(logging.WARNING)

MAX_MEDIA = 4 * 1024 * 1024


class TelegramError(Exception):
    def __init__(self, status=0, retry_after=0):
        self.status = status
        self.retry_after = retry_after


class MediaTooLarge(Exception):
    pass


class TelegramAPI:
    def __init__(self, client: httpx.Client, token: str):
        self.client = client
        self.api_path = f"/bot{token}"
        self.file_path = f"/file/bot{token}"

    def call(self, method, **data):
        try:
            response = self.client.post(f"{self.api_path}/{method}", json=data)
            body = response.json()
            if not body.get("ok"):
                raise TelegramError(body.get("error_code", response.status_code),
                                    body.get("parameters", {}).get("retry_after", 0))
            return body["result"]
        except (httpx.HTTPError, ValueError, KeyError, AttributeError):
            raise TelegramError() from None

    def download(self, media):
        if media.get("file_size", 0) > MAX_MEDIA:
            raise MediaTooLarge
        file = self.call("getFile", file_id=media["file_id"])
        if file.get("file_size", 0) > MAX_MEDIA:
            raise MediaTooLarge
        try:
            with self.client.stream("GET", f"{self.file_path}/{file['file_path']}") as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    if len(data) + len(chunk) > MAX_MEDIA:
                        raise MediaTooLarge
                    data.extend(chunk)
            return bytes(data)
        except (httpx.HTTPError, KeyError):
            raise TelegramError() from None

    def send(self, chat_id, text):
        # Keep each plain-text response within Telegram's message limit.
        for start in range(0, len(text), 2000):
            self.call("sendMessage", chat_id=chat_id, text=text[start:start + 2000])
