# 🚀 Railway CLI Commands Cheatsheet

## **Project Setup**

```bash
railway login                           # Login to Railway
railway init                            # Create new project
railway link                            # Link existing project
railway status                          # Show project info
```

## **Services Management**

```bash
railway add -d postgres                 # Add PostgreSQL database
railway add -d redis                   # Add Redis database
railway add -d mysql                   # Add MySQL database
railway add -d mongo                   # Add MongoDB database
railway add -s                         # Add application service
railway add -s my-service              # Add named service
```

## **Environment Variables**

```bash
railway variables                       # View all variables
railway variables -k                   # View in key=value format
railway variables --json               # View in JSON format
railway variables --set "KEY=value"    # Set single variable
railway variables --set "KEY1=val1" --set "KEY2=val2"  # Set multiple
railway variables --json > backup.json # Export variables
```

## **Deployment**

```bash
railway up                             # Deploy application
railway redeploy                       # Redeploy latest version
railway down                           # Remove latest deployment
```

## **Monitoring & Debugging**

```bash
railway logs                           # View logs
railway logs --tail                   # Follow logs in real-time
railway shell                         # Open shell in deployed app
railway ssh                           # SSH into service
railway connect postgres              # Connect to PostgreSQL
railway connect redis                 # Connect to Redis
```

## **Domain Management**

```bash
railway domain                         # List domains
railway domain add api-staging.trazo.io # Add custom domain
```

## **Project Management**

```bash
railway open                           # Open project in browser
railway list                           # List all projects
railway unlink                         # Unlink current directory
railway whoami                         # Show current user
```

## **Quick Deployment Flow**

```bash
# 1. Setup
railway login
railway init

# 2. Add services
railway add -d postgres
railway add -d redis

# 3. Set environment variables
railway variables --set "SECRET_KEY=your-secret-key"
railway variables --set "DEBUG=False"

# 4. Deploy
railway up

# 5. Monitor
railway logs --tail
```

## **Environment Variables for Trazo Staging**

```bash
# Core Django
railway variables --set "SECRET_KEY=your-secret-key-here"
railway variables --set "DEBUG=False"
railway variables --set "ENVIRONMENT=staging"
railway variables --set "DJANGO_SETTINGS_MODULE=backend.settings.prod"

# URLs and CORS
railway variables --set "BASE_URL=https://api-staging.trazo.io/"
railway variables --set "FRONTEND_URL=https://app-staging.trazo.io"
railway variables --set "CSRF_TRUSTED_ORIGINS=https://api-staging.trazo.io,https://app-staging.trazo.io"

# USDA APIs (required)
railway variables --set "USDA_API_KEY=your-usda-key"
railway variables --set "USDA_NASS_API_KEY=your-nass-key"

# AWS S3
railway variables --set "AWS_ACCESS_KEY_ID=your-aws-key"
railway variables --set "AWS_SECRET_ACCESS_KEY=your-aws-secret"
railway variables --set "AWS_STORAGE_BUCKET_NAME=trazo-staging-media"

# SendGrid Email
railway variables --set "SENDGRID_API_KEY=your-sendgrid-key"
railway variables --set "FROM_EMAIL_ADDRESS=noreply@trazo.io"

# OpenAI
railway variables --set "OPENAI_API_KEY=your-openai-key"

# Blockchain (testnet)
railway variables --set "BLOCKCHAIN_ENABLED=true"
railway variables --set "POLYGON_RPC_URL=https://rpc-amoy.polygon.technology/"
railway variables --set "BLOCKCHAIN_PRIVATE_KEY=your-testnet-private-key"
```

## **Common Troubleshooting**

```bash
# Check deployment status
railway status

# View recent logs
railway logs

# Debug in shell
railway shell
python manage.py check --deploy

# Test database connection
railway connect postgres
\l  # List databases

# Restart service
railway redeploy
```

---

**Pro Tip**: Use `railway variables --json > backup.json` to backup your environment variables before making changes!
