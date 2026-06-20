import datetime
import os
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import UUID4

from mealie.core.dependencies.dependencies import get_temporary_path
from mealie.routes._base import BaseAdminController, controller
from mealie.schema._mealie import MealieModel
from mealie.schema.admin.debug import DebugResponse
from mealie.schema.openai.general import OpenAIText
from mealie.services.openai import OpenAILocalImage, OpenAIService

router = APIRouter(prefix="/debug")

MAX_INSTAGRAM_COOKIES_BYTES = 200_000


class InstagramCookiesStatus(MealieModel):
    configured: bool
    exists: bool
    writable: bool
    size: int | None = None
    updated_at: datetime.datetime | None = None
    valid_netscape: bool = False
    has_instagram_cookies: bool = False
    message: str | None = None


@controller(router)
class AdminDebugController(BaseAdminController):
    @staticmethod
    def _inspect_cookie_text(text: str) -> tuple[bool, bool]:
        cookie_lines = [
            line for line in text.splitlines() if line and not line.startswith("#") and len(line.split("\t")) >= 7
        ]
        valid_netscape = bool(cookie_lines) or text.startswith("# Netscape HTTP Cookie File")
        has_instagram_cookies = any("instagram.com" in line.lower() for line in cookie_lines)
        return valid_netscape, has_instagram_cookies

    def _instagram_cookies_path(self) -> Path | None:
        if not self.settings.INSTAGRAM_COOKIES_FILE:
            return None
        return Path(self.settings.INSTAGRAM_COOKIES_FILE)

    def _instagram_cookies_status(self) -> InstagramCookiesStatus:
        cookies_path = self._instagram_cookies_path()
        if not cookies_path:
            return InstagramCookiesStatus(
                configured=False,
                exists=False,
                writable=False,
                message="INSTAGRAM_COOKIES_FILE is not configured.",
            )

        exists = cookies_path.exists()
        writable = os.access(cookies_path if exists else cookies_path.parent, os.W_OK)
        if not exists:
            return InstagramCookiesStatus(
                configured=True,
                exists=False,
                writable=writable,
                message="Cookie file is configured but not uploaded yet.",
            )

        stat = cookies_path.stat()
        with cookies_path.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(MAX_INSTAGRAM_COOKIES_BYTES)

        valid_netscape, has_instagram_cookies = self._inspect_cookie_text(text)
        return InstagramCookiesStatus(
            configured=True,
            exists=True,
            writable=writable,
            size=stat.st_size,
            updated_at=datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC),
            valid_netscape=valid_netscape,
            has_instagram_cookies=has_instagram_cookies,
            message=(
                "Cookie file is ready." if valid_netscape and has_instagram_cookies else "Cookie file looks invalid."
            ),
        )

    @router.get("/instagram-cookies", response_model=InstagramCookiesStatus)
    def get_instagram_cookies_status(self):
        return self._instagram_cookies_status()

    @router.post("/instagram-cookies", response_model=InstagramCookiesStatus)
    async def upload_instagram_cookies(self, cookies: UploadFile = File(...)):
        cookies_path = self._instagram_cookies_path()
        if not cookies_path:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "INSTAGRAM_COOKIES_FILE is not configured")

        content = await cookies.read(MAX_INSTAGRAM_COOKIES_BYTES + 1)
        if len(content) > MAX_INSTAGRAM_COOKIES_BYTES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cookie file is too large")

        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cookie file must be UTF-8 text") from e

        valid_netscape, has_instagram_cookies = self._inspect_cookie_text(text)
        if not (valid_netscape and has_instagram_cookies):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Upload a Netscape cookies.txt file containing Instagram cookies",
            )

        try:
            cookies_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = cookies_path.with_name(f".{cookies_path.name}.tmp")
            temp_path.write_bytes(content)
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, cookies_path)
        except OSError as e:
            self.logger.exception("Failed to write Instagram cookies file")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to write cookie file") from e

        return self._instagram_cookies_status()

    @router.post("/openai/{provider_id}", response_model=DebugResponse)
    async def debug_openai(self, provider_id: UUID4, image: UploadFile | None = File(None)):
        provider = self.repos.group_ai_providers.get_one(provider_id)
        if not provider:
            return DebugResponse(success=False, response="Provider not found")

        with get_temporary_path() as temp_path:
            if image:
                if not image.filename:
                    return DebugResponse(success=False, response="Invalid image filename")
                safe_filename = Path(image.filename).name
                local_image_path = temp_path.joinpath(safe_filename)
                with local_image_path.open("wb") as buffer:
                    shutil.copyfileobj(image.file, buffer)
                local_images = [OpenAILocalImage(filename=os.path.basename(local_image_path), path=local_image_path)]
            else:
                local_images = None

            try:
                openai_service = OpenAIService(self.repos)
                prompt = openai_service.get_prompt("general.debug")

                message = "Hello, checking to see if I can reach you."
                if local_images:
                    message = f"{message} Here is an image to test with:"

                response = await openai_service.get_response(
                    prompt, message, response_schema=OpenAIText, attachments=local_images, provider=provider
                )

                if not response:
                    raise Exception("No response received from OpenAI")

                return DebugResponse(success=True, response=f'OpenAI is working. Response: "{response.text}"')

            except Exception as e:
                self.logger.exception(e)
                return DebugResponse(
                    success=False,
                    response=f'OpenAI request failed. Full error has been logged. {e.__class__.__name__}: "{e}"',
                )
