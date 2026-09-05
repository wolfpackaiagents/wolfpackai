"""Channel-neutral messaging contracts and adapters."""

from .adapters import DiscordAdapter, SlackAdapter, TelegramAdapter, WebChatAdapter
from .amp import AmpWebChatAdapter
from .contracts import ChannelIdentity, DeliveryReceipt, InboundMessage

__all__ = ["AmpWebChatAdapter", "ChannelIdentity", "DeliveryReceipt", "DiscordAdapter", "InboundMessage", "SlackAdapter", "TelegramAdapter", "WebChatAdapter"]
