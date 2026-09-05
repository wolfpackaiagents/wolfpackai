"""Map browser messages to a channel-scoped Chat sender."""

from wolfpack.channels import ChannelIdentity, DeliveryReceipt, WebChatAdapter


class LocalChat:
    def send(self, message: str, identity: ChannelIdentity, *, idempotency_key: str) -> DeliveryReceipt:
        print(f"{identity.session_key}: {message} ({idempotency_key})")
        return DeliveryReceipt(delivery_id="local-run", status="accepted")


adapter = WebChatAdapter(LocalChat(), scope="acme-support")
receipt = adapter.receive("Where is my order?", user_id="customer-7", conversation_id="browser-tab-3", message_id="message-1")
print(receipt.model_dump())
