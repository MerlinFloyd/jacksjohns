# Google Cloud Storage bucket for video output

# GCS bucket for storing generated videos
resource "google_storage_bucket" "video_output" {
  name          = "${var.project_id}-video-output"
  location      = var.region
  project       = var.project_id
  force_destroy = false

  # Use standard storage class for cost efficiency
  storage_class = "STANDARD"

  # Enable uniform bucket-level access (recommended)
  uniform_bucket_level_access = true

  # Lifecycle rule to delete old videos after 7 days
  lifecycle_rule {
    condition {
      age = 7 # days
    }
    action {
      type = "Delete"
    }
  }

  # Enable versioning for safety (optional, can be disabled to save costs)
  versioning {
    enabled = false
  }

  # CORS configuration to allow Discord to fetch videos
  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Content-Length"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.required_apis]
}

# Grant agent service account permission to write to the bucket
resource "google_storage_bucket_iam_member" "agent_video_writer" {
  bucket = google_storage_bucket.video_output.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.agent_service.email}"
}

# Grant agent service account permission to read from the bucket
resource "google_storage_bucket_iam_member" "agent_video_reader" {
  bucket = google_storage_bucket.video_output.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.agent_service.email}"
}

# Make objects publicly readable so Discord can access the video URLs
# This is necessary for Discord to embed the videos
resource "google_storage_bucket_iam_member" "public_reader" {
  bucket = google_storage_bucket.video_output.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
