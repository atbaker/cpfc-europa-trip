resource "google_compute_backend_bucket" "frontend" {
  name        = "${local.prefix}-frontend"
  project     = var.project_id
  bucket_name = google_storage_bucket.frontend.name
  enable_cdn  = true

  compression_mode = "AUTOMATIC"

  cdn_policy {
    cache_mode        = "USE_ORIGIN_HEADERS"
    negative_caching  = true
    serve_while_stale = 86400
  }

  depends_on = [google_storage_bucket_iam_member.frontend_public]
}

resource "google_compute_region_network_endpoint_group" "api" {
  name                  = "${local.prefix}-api-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.api.name
  }
}

resource "google_compute_backend_service" "api" {
  name                  = "${local.prefix}-api"
  project               = var.project_id
  protocol              = "HTTP"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  enable_cdn            = false
  timeout_sec           = 3600

  backend {
    group = google_compute_region_network_endpoint_group.api.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

resource "google_compute_global_address" "edge" {
  name         = "${local.prefix}-edge"
  project      = var.project_id
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

resource "google_compute_url_map" "https" {
  name            = "${local.prefix}-https"
  project         = var.project_id
  default_service = google_compute_backend_bucket.frontend.id

  host_rule {
    hosts        = [var.domain]
    path_matcher = "app"
  }

  path_matcher {
    name            = "app"
    default_service = google_compute_backend_bucket.frontend.id

    path_rule {
      paths = [
        "/api",
        "/api/*",
        "/healthz",
        "/readyz",
      ]
      service = google_compute_backend_service.api.id
    }
  }

  test {
    host    = var.domain
    path    = "/api/fixtures"
    service = google_compute_backend_service.api.id
  }

  test {
    host    = var.domain
    path    = "/_next/static/example.js"
    service = google_compute_backend_bucket.frontend.id
  }
}

resource "google_compute_url_map" "http_redirect" {
  name    = "${local.prefix}-http-redirect"
  project = var.project_id

  default_url_redirect {
    host_redirect          = var.domain
    https_redirect         = true
    redirect_response_code = "PERMANENT_REDIRECT"
    strip_query            = false
  }
}

resource "google_certificate_manager_dns_authorization" "app" {
  name     = "${local.prefix}-dns"
  project  = var.project_id
  location = "global"
  domain   = var.domain

  depends_on = [google_project_service.required]
}

resource "google_certificate_manager_certificate" "app" {
  name     = "${local.prefix}-edge"
  project  = var.project_id
  location = "global"

  managed {
    domains            = [var.domain]
    dns_authorizations = [google_certificate_manager_dns_authorization.app.id]
  }
}

resource "google_certificate_manager_certificate_map" "app" {
  name    = "${local.prefix}-edge"
  project = var.project_id
}

resource "google_certificate_manager_certificate_map_entry" "app" {
  name         = "${local.prefix}-edge"
  project      = var.project_id
  map          = google_certificate_manager_certificate_map.app.name
  hostname     = var.domain
  certificates = [google_certificate_manager_certificate.app.id]
}

resource "google_compute_ssl_policy" "edge" {
  name            = "${local.prefix}-edge"
  project         = var.project_id
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

resource "google_compute_target_https_proxy" "edge" {
  name            = "${local.prefix}-https"
  project         = var.project_id
  url_map         = google_compute_url_map.https.id
  ssl_policy      = google_compute_ssl_policy.edge.id
  certificate_map = "//certificatemanager.googleapis.com/${google_certificate_manager_certificate_map.app.id}"
}

resource "google_compute_target_http_proxy" "redirect" {
  name    = "${local.prefix}-http"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${local.prefix}-https"
  project               = var.project_id
  target                = google_compute_target_https_proxy.edge.id
  ip_address            = google_compute_global_address.edge.id
  port_range            = "443"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  network_tier          = "PREMIUM"
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${local.prefix}-http"
  project               = var.project_id
  target                = google_compute_target_http_proxy.redirect.id
  ip_address            = google_compute_global_address.edge.id
  port_range            = "80"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  network_tier          = "PREMIUM"
}
