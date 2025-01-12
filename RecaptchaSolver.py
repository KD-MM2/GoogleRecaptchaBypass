import os
import urllib.request
import random
import pydub
import speech_recognition
import time
from typing import Optional
from patchright.async_api import Page


class RecaptchaSolver:
    """A class to solve reCAPTCHA challenges using audio recognition with Playwright."""

    # Constants
    TEMP_DIR = os.getenv("TEMP") if os.name == "nt" else "/tmp"
    TIMEOUT_STANDARD = 7000  # Playwright uses milliseconds
    TIMEOUT_SHORT = 1000
    TIMEOUT_DETECTION = 50

    def __init__(self, page: Page) -> None:
        """Initialize the solver with a Playwright page.

        Args:
            page: Playwright Page instance for browser interaction
        """
        self.page = page

    def get_selector(self, selector: str) -> str:
        selectors = {
            "checkbox": ".rc-anchor-content",
            "audio_challenge": "#recaptcha-audio-button",
            "audio_response": "#audio-response",
            "verify_button": "#recaptcha-verify-button",
            "token": "#recaptcha-token",
            "iframe": "iframe[title='reCAPTCHA']",
            "challenge_frame": "iframe[title*='recaptcha challenge']",
            "checkmark": ".recaptcha-checkbox-checkmark",
            "error_message": "text='Try again later'",
            "audio_source": "#audio-source",
        }
        return selectors.get(selector, "")

    async def solveCaptcha(self) -> None:
        """Attempt to solve the reCAPTCHA challenge.

        Raises:
            Exception: If captcha solving fails or bot is detected
        """
        # Handle main reCAPTCHA iframe
        iframe_handle = await self.page.wait_for_selector(self.get_selector("iframe"), timeout=self.TIMEOUT_STANDARD)

        if not iframe_handle:
            raise Exception("Cannot find reCAPTCHA iframe")

        frame = await iframe_handle.content_frame()
        if not frame:
            raise Exception("Cannot access iframe content")

        # Click the checkbox
        await frame.wait_for_selector(self.get_selector("checkbox"), timeout=self.TIMEOUT_STANDARD)
        await frame.click(self.get_selector("checkbox"))

        # Check if solved by just clicking
        if await self.is_solved():
            return

        # Handle audio challenge
        challenge_frame = await self.page.wait_for_selector(self.get_selector("challenge_frame"), timeout=self.TIMEOUT_STANDARD)

        if not challenge_frame:
            raise Exception("Cannot find challenge iframe")

        frame = await challenge_frame.content_frame()
        if not frame:
            raise Exception("Cannot access challenge iframe")

        # Click audio button
        await frame.wait_for_selector(self.get_selector("audio_challenge"), timeout=self.TIMEOUT_STANDARD)
        await frame.click(self.get_selector("audio_challenge"))
        await self.page.wait_for_timeout(300)  # equivalent to time.sleep(0.3)

        if await self.is_detected():
            raise Exception("Captcha detected bot behavior")

        # Modified audio source handling - wait for element regardless of visibility
        try:
            audio_element = await frame.wait_for_selector(
                self.get_selector("audio_source"), timeout=self.TIMEOUT_STANDARD, state="attached"  # Changed from default "visible" state
            )

            if not audio_element:
                raise Exception("Cannot find audio source element")

            audio_source = await audio_element.get_attribute("src")
            if not audio_source:
                raise Exception("Audio source URL not found")

            text_response = await self._process_audio_challenge(audio_source)
            await frame.fill(self.get_selector("audio_response"), text_response.lower())
            await frame.click(self.get_selector("verify_button"))
            await self.page.wait_for_timeout(400)

            if not await self.is_solved():
                raise Exception("Failed to solve the captcha")

        except Exception as e:
            raise Exception(f"Audio challenge failed: {str(e)}")

    async def _process_audio_challenge(self, audio_url: str) -> str:
        """Process the audio challenge and return the recognized text.

        Args:
            audio_url: URL of the audio file to process

        Returns:
            str: Recognized text from the audio file
        """
        mp3_path = os.path.join(self.TEMP_DIR, f"{random.randrange(1,1000)}.mp3")
        wav_path = os.path.join(self.TEMP_DIR, f"{random.randrange(1,1000)}.wav")

        try:
            urllib.request.urlretrieve(audio_url, mp3_path)
            sound = pydub.AudioSegment.from_mp3(mp3_path)
            sound.export(wav_path, format="wav")

            recognizer = speech_recognition.Recognizer()
            with speech_recognition.AudioFile(wav_path) as source:
                audio = recognizer.record(source)

            return recognizer.recognize_google(audio)

        finally:
            for path in (mp3_path, wav_path):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    async def is_solved(self) -> bool:
        """Check if the captcha has been solved successfully."""
        try:
            iframe = await self.page.wait_for_selector(self.get_selector("iframe"), timeout=self.TIMEOUT_SHORT)
            if not iframe:
                return False

            frame = await iframe.content_frame()
            if not frame:
                return False

            checkmark = await frame.wait_for_selector(self.get_selector("checkmark"), timeout=self.TIMEOUT_SHORT)
            return checkmark is not None and await checkmark.get_attribute("style") is not None
        except Exception:
            return False

    async def is_detected(self) -> bool:
        """Check if the bot has been detected."""
        try:
            challenge_frame = await self.page.wait_for_selector(self.get_selector("challenge_frame"), timeout=self.TIMEOUT_DETECTION)
            if not challenge_frame:
                return False

            frame = await challenge_frame.content_frame()
            if not frame:
                return False

            error_message = await frame.query_selector(self.get_selector("error_message"))
            return error_message is not None and await error_message.is_visible()
        except Exception:
            return False

    async def get_token(self) -> Optional[str]:
        """Get the reCAPTCHA token if available."""
        try:
            challenge_frame = await self.page.wait_for_selector(self.get_selector("challenge_frame"))
            if not challenge_frame:
                return None

            frame = await challenge_frame.content_frame()
            if not frame:
                return None

            token_element = await frame.wait_for_selector(self.get_selector("token"))
            return await token_element.get_attribute("value") if token_element else None
        except Exception:
            return None
