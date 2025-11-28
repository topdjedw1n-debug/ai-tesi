#!/bin/bash
# Скрипт для створення admin користувача для тестування

set -e

echo "🔧 Creating admin user for testing..."

# Database connection
DB_CONTAINER="ai-thesis-postgres"
DB_NAME="ai_thesis_platform"
DB_USER="postgres"

# Admin credentials
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@tesigo.com}"
ADMIN_NAME="${ADMIN_NAME:-Admin User}"

echo "📧 Email: $ADMIN_EMAIL"
echo "👤 Name: $ADMIN_NAME"

# Check if container exists
if ! docker ps | grep -q "$DB_CONTAINER"; then
    echo "❌ Database container '$DB_CONTAINER' not running!"
    echo "Start it with: cd infra/docker && docker-compose up -d postgres"
    exit 1
fi

# Create or update admin user
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" << EOF
-- Check if user exists
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE email = '$ADMIN_EMAIL') THEN
        -- Update existing user to be admin
        UPDATE users 
        SET is_admin = true,
            is_super_admin = true,
            is_active = true,
            is_verified = true,
            full_name = '$ADMIN_NAME'
        WHERE email = '$ADMIN_EMAIL';
        
        RAISE NOTICE 'Updated existing user to admin: %', '$ADMIN_EMAIL';
    ELSE
        -- Create new admin user
        INSERT INTO users (
            email, 
            full_name, 
            is_admin, 
            is_super_admin, 
            is_active, 
            is_verified,
            created_at,
            updated_at
        ) VALUES (
            '$ADMIN_EMAIL',
            '$ADMIN_NAME',
            true,
            true,
            true,
            true,
            NOW(),
            NOW()
        );
        
        RAISE NOTICE 'Created new admin user: %', '$ADMIN_EMAIL';
    END IF;
END \$\$;

-- Show admin user details
SELECT 
    id,
    email,
    full_name,
    is_admin,
    is_super_admin,
    is_active,
    created_at
FROM users 
WHERE email = '$ADMIN_EMAIL';
EOF

echo ""
echo "✅ Admin user created/updated!"
echo ""
echo "🔐 Login credentials:"
echo "   Email:    $ADMIN_EMAIL"
echo "   Password: admin123"
echo ""
echo "📝 Test login:"
echo "curl -X POST http://localhost:8000/api/v1/auth/admin/simple-login \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"email\": \"$ADMIN_EMAIL\", \"password\": \"admin123\"}'"
echo ""
