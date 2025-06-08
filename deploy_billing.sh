#!/bin/bash

# Trazo Billing Deployment Script
# ================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
FORCE=false

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Show usage
show_usage() {
    echo "Trazo Billing Deployment Script"
    echo "================================"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Environment (development, staging, production)"
    echo "  -f, --force             Force recreation of existing plans"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --environment development"
    echo "  $0 --environment staging --force"
    echo "  $0 --environment production"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    print_error "Valid environments: development, staging, production"
    exit 1
fi

print_status "🚀 Starting Trazo billing deployment for $ENVIRONMENT"
echo "=================================================="

# Check if we're in the right directory
if [[ ! -f "manage.py" ]]; then
    print_error "manage.py not found. Please run this script from the trazo-back directory."
    exit 1
fi

# Check if Poetry is available
if ! command -v poetry &> /dev/null; then
    print_error "Poetry is not installed or not in PATH"
    print_error "Please install Poetry: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Install dependencies
print_status "📦 Installing dependencies..."
poetry install --no-dev

# Check environment variables
print_status "🔧 Validating environment configuration..."
if poetry run python setup_billing.py --validate-only; then
    print_success "Environment validation passed"
else
    print_error "Environment validation failed"
    print_error "Please check your .env file and Stripe configuration"
    exit 1
fi

# Apply database migrations
print_status "🗄️  Applying database migrations..."
poetry run python manage.py migrate

# Prepare command arguments
COMMAND_ARGS="--environment $ENVIRONMENT"
if [[ "$FORCE" == true ]]; then
    COMMAND_ARGS="$COMMAND_ARGS --force"
    print_warning "Force mode enabled - existing plans will be recreated"
fi

# Run the billing setup
print_status "💳 Setting up billing plans and add-ons..."
if poetry run python setup_billing.py $COMMAND_ARGS; then
    print_success "Billing setup completed successfully!"
else
    print_error "Billing setup failed!"
    exit 1
fi

# Environment-specific post-deployment steps
case $ENVIRONMENT in
    development)
        print_status "🧪 Development environment setup complete"
        echo "Next steps:"
        echo "  1. Visit: http://localhost:3000/admin/dashboard/pricing"
        echo "  2. Test with Stripe test cards"
        echo "  3. Check webhook endpoints"
        ;;
    staging)
        print_status "🚦 Staging environment setup complete"
        echo "Next steps:"
        echo "  1. Test all pricing flows"
        echo "  2. Verify Stripe webhooks"
        echo "  3. Run automated tests"
        ;;
    production)
        print_status "🌟 Production environment setup complete"
        print_warning "⚠️  Important production checklist:"
        echo "  1. ✅ Live Stripe keys configured"
        echo "  2. ✅ Webhook endpoints verified"
        echo "  3. ✅ SSL certificates valid"
        echo "  4. ✅ Monitoring alerts configured"
        echo "  5. ✅ Backup strategy in place"
        ;;
esac

print_success "🎉 Deployment completed successfully!"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Timestamp: $(date)"
echo "==================================================" 