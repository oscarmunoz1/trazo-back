#!/bin/bash

# Trazo Backend - Railway Staging Deployment Script
# Usage: ./deploy-to-railway.sh

set -e  # Exit on any error

echo "🚀 Starting Trazo Backend deployment to Railway..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI is not installed.${NC}"
    echo -e "${BLUE}Install it with: npm install -g @railway/cli${NC}"
    exit 1
fi

# Check if user is logged in
if ! railway whoami &> /dev/null; then
    echo -e "${YELLOW}⚠️  You're not logged in to Railway.${NC}"
    echo -e "${BLUE}Logging you in...${NC}"
    railway login
fi

echo -e "${GREEN}✅ Railway CLI is ready${NC}"

# Navigate to trazo-back directory
if [ ! -f "manage.py" ]; then
    if [ -d "trazo-back" ]; then
        cd trazo-back
        echo -e "${BLUE}📁 Navigated to trazo-back directory${NC}"
    else
        echo -e "${RED}❌ Could not find trazo-back directory or manage.py${NC}"
        exit 1
    fi
fi

# Check if project exists
if [ ! -f ".railway" ]; then
    echo -e "${YELLOW}⚠️  No Railway project linked.${NC}"
    echo -e "${BLUE}Initializing new Railway project...${NC}"
    
    railway init
    
    echo -e "${GREEN}✅ Railway project initialized${NC}"
    echo -e "${YELLOW}📝 Adding PostgreSQL and Redis services...${NC}"
    
    # Add PostgreSQL
    echo -e "${BLUE}Adding PostgreSQL database...${NC}"
    railway add -d postgres
    
    # Add Redis
    echo -e "${BLUE}Adding Redis database...${NC}"
    railway add -d redis
    
    echo -e "${GREEN}✅ Database services added${NC}"
fi

# Check if essential environment variables are set
echo -e "${BLUE}🔍 Checking environment variables...${NC}"

# Generate SECRET_KEY if not exists
if ! railway variables | grep -q "SECRET_KEY"; then
    echo -e "${YELLOW}⚠️  SECRET_KEY not set. Generating one...${NC}"
    SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    railway variables --set "SECRET_KEY=$SECRET_KEY"
    echo -e "${GREEN}✅ SECRET_KEY generated and set${NC}"
fi

# Set basic Django settings
echo -e "${BLUE}Setting basic Django environment variables...${NC}"
railway variables --set "DEBUG=False" --set "ENVIRONMENT=staging" --set "DJANGO_SETTINGS_MODULE=backend.settings.prod"

echo -e "${GREEN}✅ Basic environment variables set${NC}"

# Deploy the application
echo -e "${BLUE}🚀 Deploying to Railway...${NC}"
railway up

echo -e "${GREEN}✅ Deployment initiated!${NC}"

# Show deployment logs
echo -e "${BLUE}📋 Showing deployment logs...${NC}"
railway logs --tail

echo ""
echo -e "${GREEN}🎉 Deployment complete!${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo -e "${BLUE}   1. Set up custom domain in Railway dashboard${NC}"
echo -e "${BLUE}   2. Configure all environment variables (see staging-environment-template.txt)${NC}"
echo -e "${BLUE}   3. Run database migrations${NC}"
echo -e "${BLUE}   4. Test the deployment${NC}"
echo ""
echo -e "${BLUE}🔧 Useful commands:${NC}"
echo -e "${BLUE}   railway logs                              - View logs${NC}"
echo -e "${BLUE}   railway logs --tail                       - Follow logs${NC}"
echo -e "${BLUE}   railway shell                             - Open shell${NC}"
echo -e "${BLUE}   railway variables                         - View variables${NC}"
echo -e "${BLUE}   railway variables --set \"KEY=value\"        - Set variable${NC}"
echo -e "${BLUE}   railway open                              - Open in browser${NC}"
echo -e "${BLUE}   railway connect postgres                  - Connect to database${NC}"
echo ""
echo -e "${GREEN}Happy deploying! 🚀${NC}" 