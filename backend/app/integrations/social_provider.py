"""Provider contracts. Official OAuth/API adapters are not implemented yet."""
class SocialProvider:
    def __init__(self, credentials=None):
        self.credentials = credentials or {}

    def connect(self, auth_code=None):
        raise NotImplementedError("Official OAuth adapter is not implemented")

    def disconnect(self):
        raise NotImplementedError("Token revocation is not implemented")

    def refresh_token(self):
        raise NotImplementedError("Token refresh is not implemented")

    def publish(self, content_data):
        raise NotImplementedError("Publishing adapter is not implemented")

    def get_post_status(self, post_id):
        raise NotImplementedError("Post status adapter is not implemented")

    def get_analytics(self, account_id, date_range):
        raise NotImplementedError("Analytics adapter is not implemented")

    def delete_post(self, post_id):
        raise NotImplementedError("Post deletion adapter is not implemented")

class YouTubeProvider(SocialProvider):
    platform = "youtube"

class MetaProvider(SocialProvider):
    platform = "meta"

class TikTokProvider(SocialProvider):
    platform = "tiktok"
