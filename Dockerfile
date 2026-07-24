FROM ghcr.io/ministryofjustice/analytical-platform-airflow-python-base:1.38.0@sha256:6d5673d45c3c05b04a3f8c1ae3b24c5472ae753b9d1e5e822507995643b34abe
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
