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
  platforms = ["linux/arm64/v8", "linux/amd64"]
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
  platforms = ["linux/arm64/v8", "linux/amd64"]
  tags = ["ghcr.io/fossinating/tarheel-compass-data:staging"]
}

target "data-release" {
  inherits = ["data-staging"]
  tags = ["ghcr.io/fossinating/tarheel-compass-data:latest"]
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
  platforms = ["linux/arm64/v8", "linux/amd64"]
  tags = ["ghcr.io/fossinating/tarheel-compass-server:staging"]
}

target "server-release" {
  inherits = ["server-staging"]
  tags = ["ghcr.io/fossinating/tarheel-compass-server:latest"]
}