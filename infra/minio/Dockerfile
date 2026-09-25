ARG GO_VERSION=1.24

FROM golang:${GO_VERSION}-alpine AS builder

ARG MINIO_VERSION

RUN test -n "${MINIO_VERSION}"
RUN GOBIN=/out CGO_ENABLED=0 go install github.com/minio/minio@${MINIO_VERSION}

FROM alpine:3.23

RUN apk add --no-cache ca-certificates \
    && addgroup -S minio \
    && adduser -S -G minio minio \
    && mkdir -p /data \
    && chown -R minio:minio /data

COPY --from=builder /out/minio /usr/local/bin/minio

USER minio

EXPOSE 9000 9001
VOLUME ["/data"]

ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
