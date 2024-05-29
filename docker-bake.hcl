# docker-bake.hcl
group "default" {
  targets = ["data-dev", "server-dev"]
}

group "staging" {
  targets = ["data-staging", "server-staging"]
}

group "release" {
  targets = ["data-release", "server-release"]
}

target "common" {
  dockerfile = "Dockerfile.common"
}

target "data-dev" {
  contexts = {
    common = "target:common"
  }
  dockerfile = "Dockerfile.data"
  tags = ["tarheel-compass-data"]
}

target "data-staging" {
  inherits = ["data-dev"]
  platforms = ["linux/arm/v7", "linux/arm64/v8", "linux/amd64"]
  tags = ["ghcr.io/fossinating/tarheel-compass-data"]
}

target "data-release" {
  inherits = ["data-staging"]
}

target "server-dev" {
  contexts = {
    common = "target:common"
  }
  dockerfile = "Dockerfile.server"
  tags = ["tarheel-compass-server"]
}

target "server-staging" {
  inherits = ["server-dev"]
  platforms = ["linux/arm/v7", "linux/arm64/v8", "linux/amd64"]
  tags = ["ghcr.io/fossinating/tarheel-compass-server"]
}

target "server-release" {
  inherits = ["server-staging"]
}