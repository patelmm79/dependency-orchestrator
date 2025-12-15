#!/bin/bash
# PostgreSQL installation and setup script for Debian 11
# Template variables: db_name, db_user, db_password

set -e

echo "Starting PostgreSQL setup..."

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
sudo -u postgres psql << 'EOF'
CREATE DATABASE ${db_name};
CREATE USER ${db_user} WITH PASSWORD '${db_password}';
GRANT ALL PRIVILEGES ON DATABASE ${db_name} TO ${db_user};
ALTER DATABASE ${db_name} OWNER TO ${db_user};
EOF

echo "PostgreSQL setup complete!"
echo "Database: ${db_name}"
echo "User: ${db_user}"
