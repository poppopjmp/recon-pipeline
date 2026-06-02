FROM python:3.12-slim

ENV LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 8082 is the default port for luigi's central scheduler
EXPOSE 8082

# OS-level dependencies (Debian base -> apt).  chromium is used by aquatone.
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        less \
        nmap \
        sudo \
        vim \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the project (and its Python dependencies) from pyproject.toml
COPY . /opt/recon-pipeline
WORKDIR /opt/recon-pipeline
RUN pip install --no-cache-dir .

# Setup workarounds:
# - systemctl stub: systemd is not present in the container and the luigid
#   service setup expects it; more trouble than it's worth otherwise.
# - symlink the interactive shell to /bin/pipeline for `docker exec -it ... pipeline`.
# - the default interface inside the container is eth0, not tun0.
RUN touch /usr/bin/systemctl && chmod 755 /usr/bin/systemctl \
    && ln -s /opt/recon-pipeline/pipeline/recon-pipeline.py /bin/pipeline \
    && sed -i 's/tun0/eth0/g' /opt/recon-pipeline/pipeline/recon/config.py

# luigid is installed on PATH by pip; run the central scheduler by default
WORKDIR /root/.local/recon-pipeline/files
CMD ["luigid", "--pidfile", "/var/run/luigid.pid", "--logdir", "/var/log"]
