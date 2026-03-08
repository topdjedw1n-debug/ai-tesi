#!/bin/bash
# ============================================================================
# AI Thesis - EC2 Server Initial Setup Script
# ============================================================================
# This script prepares a clean EC2 instance for running the AI Thesis platform
# Run this ONCE on a new EC2 instance before first deployment
# ============================================================================

set -e

echo "🚀 Starting EC2 server setup for AI Thesis..."
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}❌ Please run as normal user, not root!${NC}"
    exit 1
fi

# ============================================================================
# 1. System Update
# ============================================================================
echo -e "\n${GREEN}📦 Step 1: Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# ============================================================================
# 2. Install Docker
# ============================================================================
echo -e "\n${GREEN}🐳 Step 2: Installing Docker...${NC}"

# Remove old versions if any
sudo apt-get remove -y docker docker-engine docker.io containerd runc || true

# Install prerequisites
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
sudo usermod -aG docker $USER

echo -e "${YELLOW}⚠️  You need to log out and back in for docker group changes to take effect!${NC}"

# ============================================================================
# 3. Install Docker Compose (standalone)
# ============================================================================
echo -e "\n${GREEN}🔧 Step 3: Installing Docker Compose...${NC}"

DOCKER_COMPOSE_VERSION="2.24.5"
sudo curl -L "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# ============================================================================
# 4. Install Git
# ============================================================================
echo -e "\n${GREEN}📚 Step 4: Installing Git...${NC}"
sudo apt-get install -y git

# ============================================================================
# 5. Configure Firewall (UFW)
# ============================================================================
echo -e "\n${GREEN}🔥 Step 5: Configuring firewall...${NC}"

# Install UFW if not present
sudo apt-get install -y ufw

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (CRITICAL - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow application ports
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 3000/tcp  # Frontend
sudo ufw allow 9000/tcp  # MinIO
sudo ufw allow 9001/tcp  # MinIO Console

# Enable firewall
echo "y" | sudo ufw enable

sudo ufw status

# ============================================================================
# 6. Clone Repository
# ============================================================================
echo -e "\n${GREEN}📥 Step 6: Cloning repository...${NC}"

# Check if directory already exists
if [ -d "$HOME/ai-thesis" ]; then
    echo -e "${YELLOW}⚠️  Directory ~/ai-thesis already exists. Skipping clone.${NC}"
else
    cd $HOME
    git clone https://github.com/topdjedw1n-debug/ai-tesi.git ai-thesis
    cd ai-thesis
    echo -e "${GREEN}✅ Repository cloned successfully${NC}"
fi

# ============================================================================
# 7. Create necessary directories
# ============================================================================
echo -e "\n${GREEN}📁 Step 7: Creating data directories...${NC}"

cd $HOME/ai-thesis
mkdir -p data/postgres
mkdir -p data/redis
mkdir -p data/minio
mkdir -p logs

# ============================================================================
# 8. System Optimizations
# ============================================================================
echo -e "\n${GREEN}⚙️  Step 8: Applying system optimizations...${NC}"

# Increase file descriptors limit
echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf

# Configure vm.overcommit_memory for Redis
echo "vm.overcommit_memory = 1" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Disable Transparent Huge Pages (THP) for Redis
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag

# Make THP changes persistent
cat << 'EOF' | sudo tee /etc/rc.local
#!/bin/bash
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag
exit 0
EOF
sudo chmod +x /etc/rc.local

# ============================================================================
# 9. Setup automatic security updates
# ============================================================================
echo -e "\n${GREEN}🔒 Step 9: Configuring automatic security updates...${NC}"
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# ============================================================================
# 10. Install monitoring tools
# ============================================================================
echo -e "\n${GREEN}📊 Step 10: Installing monitoring tools...${NC}"
sudo apt-get install -y htop iotop nethogs

# ============================================================================
# Final Steps
# ============================================================================
echo -e "\n${GREEN}=============================================="
echo "✅ EC2 Server Setup Complete!"
echo "=============================================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. ${YELLOW}Log out and log back in${NC} (for Docker group to take effect)"
echo "   $ exit"
echo "   $ ssh user@your-server"
echo ""
echo "2. ${YELLOW}Configure GitHub Secrets${NC} in your repository:"
echo "   - Go to: https://github.com/topdjedw1n-debug/ai-tesi/settings/secrets/actions"
echo "   - Add the following secrets (see DEPLOYMENT_GUIDE.md for details)"
echo ""
echo "3. ${YELLOW}Generate and upload SSH key${NC} to GitHub Secrets:"
echo "   Run on your local machine:"
echo "   $ ssh-keygen -t rsa -b 4096 -f ~/.ssh/ai-thesis-deploy -N \"\""
echo "   $ ssh-copy-id -i ~/.ssh/ai-thesis-deploy.pub user@your-ec2-ip"
echo "   Then add the private key content to GitHub secret: EC2_SSH_KEY"
echo ""
echo "4. ${YELLOW}First Deployment:${NC}"
echo "   After setting up secrets, push to main branch or manually trigger workflow"
echo ""
echo "5. ${YELLOW}Verify everything works:${NC}"
echo "   $ cd ~/ai-thesis/infra/docker"
echo "   $ docker-compose -f docker-compose.prod.yml ps"
echo ""
echo "🌐 Your services will be available at:"
echo "   - Frontend: http://$(curl -s ifconfig.me):3000"
echo "   - Backend:  http://$(curl -s ifconfig.me):8000"
echo "   - API Docs: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Don't forget to log out and back in!${NC}"
echo "=============================================="
