FROM ghcr.io/ministryofjustice/analytical-platform-airflow-python-base:1.37.0@sha256:4e924b3b014ee0e7e52cf4fc4e7e94b44b2b4aef9248d2f21aff644528979864
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
