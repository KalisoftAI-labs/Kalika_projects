#!/bin/bash

###############################################################################
# EC2 Instance Cleanup Script
# Description: Removes unnecessary files and caches to free up disk space
# Usage: sudo ./cleanup_instance.sh (run with sudo to avoid password prompts)
# Recommended: Run daily via cron job
###############################################################################

# Don't exit on errors - continue cleaning what we can
set +e

echo "=========================================="
echo "EC2 Instance Cleanup Started"
echo "=========================================="
echo ""

# Check available disk space before cleanup
echo "Disk space BEFORE cleanup:"
df -h / | grep -v Filesystem
echo ""

# Track space freed
INITIAL_SPACE=$(df / | tail -1 | awk '{print $4}')

###############################################################################
# 1. VSCode Server Cache Cleanup
###############################################################################
echo "[1/10] Cleaning VSCode Server cache..."
if [ -d ~/.vscode-server ]; then
    rm -rf ~/.vscode-server
    echo "✓ VSCode Server cache removed"
else
    echo "✓ No VSCode Server cache found"
fi
echo ""

###############################################################################
# 2. APT Package Manager Cleanup
###############################################################################
echo "[2/10] Cleaning APT cache..."
echo "  → Running apt-get clean..."
sudo apt-get clean -y 2>&1 | grep -v "^$" || true
echo "  → Running apt-get autoclean..."
sudo apt-get autoclean -y 2>&1 | grep -v "^$" || true
echo "  → Running apt-get autoremove..."
sudo apt-get autoremove -y 2>&1 | tail -5 || true
echo "✓ APT cache cleaned"
echo ""

###############################################################################
# 3. System Logs Cleanup (older than 7 days)
###############################################################################
echo "[3/10] Cleaning old system logs..."
echo "  → Vacuuming journal logs..."
sudo journalctl --vacuum-time=7d 2>&1 | tail -3 || true
echo "✓ Old journal logs removed (kept last 7 days)"
echo ""

###############################################################################
# 4. Temporary Files Cleanup
###############################################################################
echo "[4/10] Cleaning temporary files..."
sudo rm -rf /tmp/* 2>/dev/null || true
sudo rm -rf /var/tmp/* 2>/dev/null || true
echo "✓ Temporary files removed"
echo ""

###############################################################################
# 5. Python/Pip Cache Cleanup
###############################################################################
echo "[5/10] Cleaning Python/Pip cache..."
if command -v pip3 &> /dev/null; then
    pip3 cache purge > /dev/null 2>&1 || true
    echo "✓ Pip cache purged"
fi
rm -rf ~/.cache/pip 2>/dev/null || true
echo "✓ Python cache cleaned"
echo ""

###############################################################################
# 6. Thumbnail Cache Cleanup
###############################################################################
echo "[6/10] Cleaning thumbnail cache..."
rm -rf ~/.cache/thumbnails/* 2>/dev/null || true
rm -rf ~/.thumbnails/* 2>/dev/null || true
echo "✓ Thumbnail cache removed"
echo ""

###############################################################################
# 7. Old Log Files in Application
###############################################################################
echo "[7/10] Cleaning application logs (older than 30 days)..."
if [ -d "/home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/logs" ]; then
    find /home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/logs -type f -name "*.log" -mtime +30 -delete 2>/dev/null || true
    echo "✓ Old application logs removed"
else
    echo "✓ No application logs directory found"
fi
echo ""

###############################################################################
# 8. Django Session Cleanup (if using file-based sessions)
###############################################################################
echo "[8/10] Cleaning Django sessions..."
cd /home/ubuntu/Kalika_projects/ecommerce_project/ecommerce
if [ -f "manage.py" ]; then
    source env/bin/activate 2>/dev/null || true
    python3 manage.py clearsessions > /dev/null 2>&1 || true
    deactivate 2>/dev/null || true
    echo "✓ Django sessions cleaned"
else
    echo "✓ Django manage.py not found"
fi
echo ""

###############################################################################
# 9. NPM Cache Cleanup (if Node.js is installed)
###############################################################################
echo "[9/10] Cleaning NPM cache..."
if command -v npm &> /dev/null; then
    npm cache clean --force > /dev/null 2>&1 || true
    echo "✓ NPM cache cleaned"
else
    echo "✓ NPM not installed, skipping"
fi
echo ""

###############################################################################
# 10. Docker Cleanup (if Docker is installed)
###############################################################################
echo "[10/10] Cleaning Docker resources..."
if command -v docker &> /dev/null; then
    # Remove stopped containers
    sudo docker container prune -f > /dev/null 2>&1 || true
    # Remove unused images
    sudo docker image prune -a -f > /dev/null 2>&1 || true
    # Remove unused volumes
    sudo docker volume prune -f > /dev/null 2>&1 || true
    # Remove unused networks
    sudo docker network prune -f > /dev/null 2>&1 || true
    echo "✓ Docker resources cleaned"
else
    echo "✓ Docker not installed, skipping"
fi
echo ""

###############################################################################
# Summary
###############################################################################
echo "=========================================="
echo "Cleanup Completed!"
echo "=========================================="
echo ""

# Calculate space freed
FINAL_SPACE=$(df / | tail -1 | awk '{print $4}')
FREED_SPACE=$((FINAL_SPACE - INITIAL_SPACE))

echo "Disk space AFTER cleanup:"
df -h / | grep -v Filesystem
echo ""

if [ $FREED_SPACE -gt 0 ]; then
    echo "✓ Space freed: ~$((FREED_SPACE / 1024)) MB"
else
    echo "✓ Disk space optimized"
fi

echo ""
echo "=========================================="
echo "To run this script daily, add to crontab:"
echo "crontab -e"
echo "# Add this line:"
echo "0 2 * * * /home/ubuntu/Kalika_projects/ecommerce_project/ecommerce/cleanup_instance.sh >> /home/ubuntu/cleanup.log 2>&1"
echo "=========================================="
