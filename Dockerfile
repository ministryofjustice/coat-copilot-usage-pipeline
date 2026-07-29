FROM ghcr.io/ministryofjustice/analytical-platform-airflow-python-base:1.39.0@sha256:3c208257c2fdc721535a142749ab254a53aef18cdd8a24775f12bc9a1dd10627
ARG MOJAP_IMAGE_VERSION="default"
ENV MOJAP_IMAGE_VERSION=${MOJAP_IMAGE_VERSION}

# Below is an example of how to use the base image

# Switch to root user to install packages
USER root                 
                       
# Copy requirements.txt
COPY requirements.txt requirements.txt 

# Copy application code
COPY src/ .

# Install requirements
RUN <<EOF
pip install --no-cache-dir --requirement requirements.txt
EOF

# Switch back to non-root user (analyticalplatform)
USER ${CONTAINER_UID}

# Execute main.py script
ENTRYPOINT ["python3", "main.py"]
