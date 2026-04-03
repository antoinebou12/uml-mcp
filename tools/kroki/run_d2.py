import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_D2_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "d2_bin")


async def run_go_script(input_data: str):
    try:
        logger.info("Running go script")
        process = await asyncio.create_subprocess_exec(
            _D2_BIN,
            "encode",
            input_data,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Go script execution failed with error: {stderr.decode()}")
            return None
        logger.info(f"Go script run succeeded with output: {stdout.decode()}")
        theme = "0"
        layout = "elk" or "dagre"
        return (
            f"https://api.d2lang.com/render/svg?script={stdout.decode().strip()}&layout={layout}&theme={theme}&sketch=0",
            input_data,
            f"https://play.d2lang.com/?script={stdout.decode().strip()}&layout={layout}&theme={theme}",
        )
    except Exception as e:
        logger.error(f"Go script execution failed with error: {str(e)}")
