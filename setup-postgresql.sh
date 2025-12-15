#!/bin/bash
# Setup PostgreSQL VM for Dependency Orchestrator
# Based on dev-nexus PostgreSQL setup approach

set -e

# Get project ID
if [ -f "terraform/terraform.tfstate" ] && command -v terraform &> /dev/null; then
  PROJECT_ID=$(cd terraform && terraform output -raw project_id 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID="${GCP_PROJECT_ID}"
fi

if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
fi

if [ -z "$PROJECT_ID" ]; then
  echo "❌ Error: Could not determine GCP project ID"
  exit 1
fi

# Configuration
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"
VM_NAME="orchestrator-postgres-vm"
MACHINE_TYPE="e2-micro"  # Free tier eligible
DISK_SIZE="30GB"
INTERNAL_IP="10.8.0.2"
NETWORK="default"
DB_NAME="orchestrator"
DB_USER="orchestrator"

# Generate secure password if not provided
if [ -z "$POSTGRES_PASSWORD" ]; then
  POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
  echo "Generated PostgreSQL password: $POSTGRES_PASSWORD"
  echo "⚠️  IMPORTANT: Save this password! You'll need it for deployment."
  echo ""
fi

echo "🚀 Setting up PostgreSQL VM for Dependency Orchestrator"
echo "   Project: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Zone: $ZONE"
echo "   VM: $VM_NAME"
echo "   Machine Type: $MACHINE_TYPE (free tier eligible)"
echo "   Internal IP: $INTERNAL_IP"
echo ""

# Enable required APIs
echo "📋 Enabling required APIs..."
gcloud services enable compute.googleapis.com --project=$PROJECT_ID
gcloud services enable vpcaccess.googleapis.com --project=$PROJECT_ID

# Check if VM already exists
if gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID &>/dev/null; then
  echo "✅ VM '$VM_NAME' already exists"
  EXISTING_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --project=$PROJECT_ID --format='value(networkInterfaces[0].networkIP)')
  echo "   Internal IP: $EXISTING_IP"
  echo ""
  echo "PostgreSQL connection details:"
  echo "  POSTGRES_HOST=$EXISTING_IP"
  echo "  POSTGRES_PORT=5432"
  echo "  POSTGRES_DB=$DB_NAME"
  echo "  POSTGRES_USER=$DB_USER"
  echo "  POSTGRES_PASSWORD=<your-password>"
  exit 0
fi

# Create startup script for PostgreSQL installation
cat > /tmp/postgres-startup.sh << 'STARTUP_SCRIPT'
#!/bin/bash
set -e

# Update system
apt-get update
apt-get upgrade -y

# Install PostgreSQL 15
apt-get install -y postgresql-15 postgresql-contrib-15

# Configure PostgreSQL to listen on all interfaces
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/15/main/postgresql.conf

# Configure max connections
sed -i "s/max_connections = 100/max_connections = 50/" /etc/postgresql/15/main/postgresql.conf

# Allow connections from VPC (10.8.0.0/16)
echo "host    all             all             10.8.0.0/16            md5" >> /etc/postgresql/15/main/pg_hba.conf

# Restart PostgreSQL
systemctl restart postgresql

# Wait for PostgreSQL to start
sleep 5

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE ${DB_NAME};
CREATE USER ${DB_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
EOF

echo "✅ PostgreSQL setup complete"
STARTUP_SCRIPT

# Replace placeholders in startup script
sed -i "s/\${DB_NAME}/$DB_NAME/g" /tmp/postgres-startup.sh
sed -i "s/\${DB_USER}/$DB_USER/g" /tmp/postgres-startup.sh
sed -i "s/\${POSTGRES_PASSWORD}/$POSTGRES_PASSWORD/g" /tmp/postgres-startup.sh

# Create the VM
echo "⏳ Creating PostgreSQL VM (this may take 2-3 minutes)..."
gcloud compute instances create $VM_NAME \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --machine-type=$MACHINE_TYPE \
  --network-interface=private-network-ip=$INTERNAL_IP,network-tier=PREMIUM,subnet=$NETWORK \
  --no-address \
  --metadata-from-file startup-script=/tmp/postgres-startup.sh \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
  --create-disk=auto-delete=yes,boot=yes,device-name=$VM_NAME,image=projects/debian-cloud/global/images/debian-11-bullseye-v20231212,mode=rw,size=$DISK_SIZE,type=projects/$PROJECT_ID/zones/$ZONE/diskTypes/pd-standard \
  --no-shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring \
  --labels=application=dependency-orchestrator,environment=production,managed-by=script,component=database \
  --reservation-affinity=any

echo ""
echo "✅ PostgreSQL VM created successfully!"
echo ""
echo "⏳ Waiting for PostgreSQL installation to complete (30 seconds)..."
sleep 30

# Initialize database schema
echo "📋 Initializing database schema..."
echo "You can initialize the schema by running:"
echo ""
echo "  # Copy schema file to VM"
echo "  gcloud compute scp orchestrator/a2a/postgres_schema.sql $VM_NAME:/tmp/ --zone=$ZONE"
echo ""
echo "  # SSH to VM and initialize"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -U $DB_USER -d $DB_NAME -f /tmp/postgres_schema.sql\""
echo ""

echo "📝 PostgreSQL connection details:"
echo ""
echo "  POSTGRES_HOST=$INTERNAL_IP"
echo "  POSTGRES_PORT=5432"
echo "  POSTGRES_DB=$DB_NAME"
echo "  POSTGRES_USER=$DB_USER"
echo "  POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
echo ""
echo "⚠️  IMPORTANT: Save these credentials securely!"
echo ""
echo "💡 Next steps:"
echo "  1. Store password in Secret Manager:"
echo "     echo -n \"$POSTGRES_PASSWORD\" | gcloud secrets create postgres-password --data-file=-"
echo ""
echo "  2. Update your terraform.tfvars with:"
echo "     use_postgresql = true"
echo "     postgres_host  = \"$INTERNAL_IP\""
echo ""
echo "  3. Deploy the orchestrator:"
echo "     ./deploy-gcp-cloudbuild.sh"
echo ""
echo "Estimated monthly cost: ~\$5-10 (e2-micro + 30GB disk, eligible for free tier)"

# Cleanup
rm -f /tmp/postgres-startup.sh
