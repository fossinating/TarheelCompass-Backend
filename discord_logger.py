import logging
from discord_webhook import DiscordWebhook, DiscordEmbed

import logging

role_pings = {
    "ERROR": "<@&1000286888554414090>",
    "WARNING": "<@&1000286850122006598>",
    "INFO": "<@&1000286794903990353>",
    "DEBUG": "",
    "SUCCESS": "<@&1000286746136821780>",
}


class DiscordLogger():
    def __init__(self, url, name: str, logger_name=None):
        self.url = url
        self.name = name
        self.debug_lines = []
        self.logger = logging.getLogger(logger_name if logger_name is not None else name.replace(" ", "-").lower())
        self.logger.setLevel(logging.DEBUG)

    def send_message(self, level, msg, color):
        return # I don't want to actually send messages for now since I'm doing local testing
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

    def debug(self, msg):
        self.logger.debug(msg)
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