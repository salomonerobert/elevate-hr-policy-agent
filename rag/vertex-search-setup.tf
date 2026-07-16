# =====================================================================
# HR Policy Agent Lab — Track A (RAG) infrastructure
#
# Provisions the Cloud Storage bucket + Vertex AI Search (Discovery Engine)
# data store and search engine used as the RAG corpus for the HR Policy Agent.
#
# Usage:
#   terraform init
#   terraform apply -var="project_id=YOUR_PROJECT_ID"
#   # ... then upload data/handbook.pdf (see rag/README.md) and run ingest-docs.py
#   terraform destroy -var="project_id=YOUR_PROJECT_ID"   # <-- clean up to avoid cost
# =====================================================================

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

# =====================================================================
# VARIABLES
# =====================================================================

variable "project_id" {
  type        = string
  description = "The GCP Project ID where resources will be provisioned."
}

variable "region" {
  type        = string
  default     = "asia-southeast1"
  description = "Regional bucket location (Singapore by default)."
}

variable "location" {
  type        = string
  default     = "global"
  description = "Vertex AI Search data store location (global, us, or eu)."
}

variable "data_store_id" {
  type        = string
  default     = "hr-policies-lab-store"
  description = "Discovery Engine data store id (match VERTEX_AI_DATA_STORE_ID in .env)."
}

variable "engine_id" {
  type        = string
  default     = "hr-policies-lab-engine"
  description = "Discovery Engine search engine id (match VERTEX_AI_SEARCH_ENGINE_ID in .env)."
}

# =====================================================================
# CLOUD STORAGE (source documents for ingestion)
# =====================================================================

resource "google_storage_bucket" "rag_source_bucket" {
  name                        = "${var.project_id}-hr-policies-source"
  location                    = var.region
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

# Upload the handbook PDF from the repo's data/ directory.
resource "google_storage_bucket_object" "policy_document" {
  name         = "handbook.pdf"
  bucket       = google_storage_bucket.rag_source_bucket.name
  source       = "${path.module}/../data/handbook.pdf"
  content_type = "application/pdf"
}

# =====================================================================
# VERTEX AI SEARCH (Discovery Engine)
# =====================================================================

resource "google_discovery_engine_data_store" "hr_policies_store" {
  location          = var.location
  data_store_id     = var.data_store_id
  display_name      = "HR Policy Lab Data Store"
  industry_vertical = "GENERIC"
  content_config    = "CONTENT_REQUIRED"
  solution_types    = ["SOLUTION_TYPE_SEARCH"]
}

resource "google_discovery_engine_search_engine" "hr_policies_search_engine" {
  location      = var.location
  engine_id     = var.engine_id
  display_name  = "HR Policy Lab Search"
  collection_id = "default_collection"
  data_store_ids = [google_discovery_engine_data_store.hr_policies_store.data_store_id]

  search_engine_config {
    search_tier = "SEARCH_TIER_ENTERPRISE"
  }
}

# Allow the Discovery Engine service agent to read the source bucket for ingestion.
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_storage_bucket_iam_member" "discovery_engine_gcs_reader" {
  bucket = google_storage_bucket.rag_source_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
}

# =====================================================================
# OUTPUTS
# =====================================================================

output "gcs_source_uri" {
  value       = "gs://${google_storage_bucket.rag_source_bucket.name}/*"
  description = "GCS URI to pass to ingest-docs.py."
}

output "data_store_id" {
  value = google_discovery_engine_data_store.hr_policies_store.data_store_id
}

output "engine_id" {
  value       = google_discovery_engine_search_engine.hr_policies_search_engine.engine_id
  description = "Set this as VERTEX_AI_SEARCH_ENGINE_ID in your .env."
}
