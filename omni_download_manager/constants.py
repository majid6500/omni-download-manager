"""Application-wide constants that do not change at runtime."""

APP_NAME = "Omni Download Manager"
APP_SHORT_NAME = "ODM"
APP_DATA_DIR_NAME = "omni-download-manager"
APP_USER_MODEL_ID = "OmniDownloadManager.ODM"
VERSION = "0.1.0"
MAX_CONCURRENT_DOWNLOADS = 5
MAX_AUTOMATIC_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 1.0

# Suffix of the temporary file a download is written to until it is complete.
PARTIAL_SUFFIX = ".part"
