FROM ghcr.io/ministryofjustice/analytical-platform-airflow-python-base:1.33.@sha256:d3600c879959aa2d716ddc22342bec42ba7fdc5124d8ac2628dd8462a0897d53
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
