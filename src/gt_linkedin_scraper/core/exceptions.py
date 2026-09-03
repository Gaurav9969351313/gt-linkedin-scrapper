class ScraperError(Exception):
    pass


class LoginFailed(ScraperError):
    pass


class RateLimitHit(ScraperError):
    pass


class ParseError(ScraperError):
    pass


class LinkedInCheckpointError(ScraperError):
    pass


class JobNotFoundError(ScraperError):
    pass
