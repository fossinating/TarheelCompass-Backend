import logging
import sys
from discord_webhook import DiscordWebhook, DiscordEmbed

role_pings = {
    "ERROR": "<@&1246049260303024148>",
    "WARNING": "<@&1246049307539275918>",
    "INFO": "<@&1246049332675870780>",
    "DEBUG": "",
    "SUCCESS": "<@&1246049390351745035>",
}


class DiscordLogger():
    def __init__(self, url, name: str, logger_name=None):
        if url is None or len(url) < 5:
            print("No discord webhook url provided, disabling discord webhook logging")
            self.url = None
        else:
            self.url = url
        self.name = name
        self.debug_lines = []
        self.logger = logging.getLogger(logger_name if logger_name is not None else name.replace(" ", "-").lower())
        self.logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def send_message(self, level, msg, color):
        if self.url is None:
            return
        webhook = DiscordWebhook(url=self.url, username=self.name, content=role_pings[level])
        embed = DiscordEmbed(title=level, description=msg, color=color)
        embed.set_timestamp()
        webhook.add_embed(embed)
        webhook.execute()

    def try_debug(self):
        if len(self.debug_lines) > 0:
            self.send_message("DEBUG", "\n".join(self.debug_lines), "968cff")
            self.debug_lines = []

    def success(self, msg):
        self.logger.info(msg)
        self.try_debug()
        self.send_message("SUCCESS", msg, "7dff7f")

    def debug(self, msg, send_discord=False):
        self.logger.debug(msg)
        if send_discord:
            self.debug_lines.append(str(msg))

    def info(self, msg):
        self.logger.info(msg)
        self.try_debug()
        self.send_message("INFO", msg, "79fcf4")

    def warning(self, msg):
        self.logger.warning(msg)
        self.try_debug()
        self.send_message("WARNING", msg, "fcb279")

    def error(self, msg):
        self.logger.error(msg)
        self.try_debug()
        self.send_message("ERROR", msg, "fc7979")