FROM ghcr.io/ministryofjustice/analytical-platform-airflow-python-base:1.40.0@sha256:2fefac06335445a58e8e2ce07936701e50bd301535f550c7c552387d1f51202d
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
