# docker-bake.dev.hcl
group "default" {
  targets = ["data"]
}

#target "webapp-dev" {
#  dockerfile = "Dockerfile.webapp"
#  tags = ["docker.io/username/webapp"]
#}

#target "webapp-release" {
#  inherits = ["webapp-dev"]
#  platforms = ["linux/amd64", "linux/arm64"]
#}

target "data" {
  dockerfile = "Dockerfile.data"
  tags = ["tarheel-compass-data"]
  platforms = ["linux/arm/v7", "linux/arm64/v8", "linux/amd64"]
}