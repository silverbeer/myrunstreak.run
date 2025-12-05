# API Gateway Migration Guide

This guide explains how to migrate from the single-repo API Gateway setup to a multi-repo architecture where:
- **runstreak-common** manages the shared API Gateway base
- **myrunstreak.com** manages service-specific routes

## Prerequisites

- Access to both repositories
- AWS CLI configured with appropriate permissions
- Terraform >= 1.5.0

## Migration Steps

### Phase 1: Deploy runstreak-common

First, deploy the runstreak-common repository to create the base API Gateway and SSM parameters.

```bash
cd /path/to/runstreak-common
cd terraform/environments/dev

# Initialize Terraform
terraform init

# Import existing API Gateway resources
# Get the current API Gateway ID from myrunstreak.com
API_ID=$(aws ssm get-parameter --name "/runstreak/shared/dev/api-gateway-id" --query 'Parameter.Value' --output text 2>/dev/null || \
         aws apigateway get-rest-apis --query "items[?name=='myrunstreak-api-dev'].id" --output text)

echo "API Gateway ID: $API_ID"

# Import the REST API
terraform import module.api_gateway_base.aws_api_gateway_rest_api.main $API_ID

# Import the stage
terraform import module.api_gateway_base.aws_api_gateway_stage.main ${API_ID}/dev

# Import the health endpoint resources
HEALTH_RESOURCE_ID=$(aws apigateway get-resources --rest-api-id $API_ID \
  --query "items[?pathPart=='health'].id" --output text)
terraform import module.api_gateway_base.aws_api_gateway_resource.health ${API_ID}/${HEALTH_RESOURCE_ID}

# Import API key
API_KEY_ID=$(aws apigateway get-api-keys --query "items[?name=='myrunstreak-personal-dev'].id" --output text)
terraform import module.api_gateway_base.aws_api_gateway_api_key.personal $API_KEY_ID

# Import usage plan
USAGE_PLAN_ID=$(aws apigateway get-usage-plans --query "items[?name=='myrunstreak-usage-plan-dev'].id" --output text)
terraform import module.api_gateway_base.aws_api_gateway_usage_plan.main $USAGE_PLAN_ID

# Plan to see what will be created/changed
terraform plan

# Apply (creates SSM parameters)
terraform apply
```

### Phase 2: Verify SSM Parameters

After deploying runstreak-common, verify the SSM parameters exist:

```bash
# List all parameters
aws ssm get-parameters-by-path \
  --path "/runstreak/shared/dev" \
  --query "Parameters[].Name"

# Expected output:
# [
#   "/runstreak/shared/dev/api-gateway-id",
#   "/runstreak/shared/dev/api-gateway-arn",
#   "/runstreak/shared/dev/api-gateway-execution-arn",
#   "/runstreak/shared/dev/api-gateway-root-resource-id",
#   "/runstreak/shared/dev/api-gateway-stage-name",
#   "/runstreak/shared/dev/api-gateway-invoke-url",
#   "/runstreak/shared/dev/api-gateway-usage-plan-id",
#   "/runstreak/shared/dev/api-gateway-api-key-id",
#   "/runstreak/shared/dev/api-gateway-cloudwatch-role-arn"
# ]
```

### Phase 3: Update myrunstreak.com

Now update myrunstreak.com to use the consumer module.

#### 3.1: Remove old API Gateway resources from Terraform state

```bash
cd /path/to/myrunstreak.com
cd terraform/environments/dev

# Remove the API Gateway base resources (now managed by runstreak-common)
terraform state rm module.api_gateway.aws_api_gateway_rest_api.main
terraform state rm module.api_gateway.aws_api_gateway_stage.main
terraform state rm module.api_gateway.aws_api_gateway_deployment.main
terraform state rm module.api_gateway.aws_api_gateway_resource.health
terraform state rm module.api_gateway.aws_api_gateway_method.health_get
terraform state rm module.api_gateway.aws_api_gateway_integration.health_mock
terraform state rm module.api_gateway.aws_api_gateway_method_response.health_get_200
terraform state rm module.api_gateway.aws_api_gateway_integration_response.health_mock
terraform state rm module.api_gateway.aws_api_gateway_api_key.personal
terraform state rm module.api_gateway.aws_api_gateway_usage_plan.main
terraform state rm module.api_gateway.aws_api_gateway_usage_plan_key.main
terraform state rm module.api_gateway.aws_api_gateway_account.main
terraform state rm module.api_gateway.aws_iam_role.api_gateway_cloudwatch
terraform state rm module.api_gateway.aws_iam_role_policy_attachment.api_gateway_cloudwatch
terraform state rm module.api_gateway.aws_cloudwatch_log_group.api_gateway
terraform state rm module.api_gateway.aws_api_gateway_method_settings.main

# Also remove any CloudWatch alarms if they exist
terraform state rm 'module.api_gateway.aws_cloudwatch_metric_alarm.api_4xx_errors[0]'
terraform state rm 'module.api_gateway.aws_cloudwatch_metric_alarm.api_5xx_errors[0]'
terraform state rm 'module.api_gateway.aws_cloudwatch_metric_alarm.api_latency[0]'
```

#### 3.2: Update main.tf to use consumer module

Edit `terraform/environments/dev/main.tf`:

1. **Remove** the `module.api_gateway` block

2. **Add** the new consumer module:
   ```hcl
   module "api_gateway_consumer" {
     source = "../../modules/api_gateway_consumer"

     environment = var.environment
     aws_region  = var.aws_region

     sync_lambda_invoke_arn    = module.lambda.function_invoke_arn
     sync_lambda_function_name = module.lambda.function_name

     query_lambda_invoke_arn    = module.lambda_query.function_invoke_arn
     query_lambda_function_name = module.lambda_query.function_name
   }
   ```

3. **Remove** the direct route definitions (lines 467-741) since they're now in the consumer module

4. **Update outputs** to reference the consumer module instead of api_gateway module

5. **Uncomment** the SSM verification step in `.github/workflows/terraform-apply.yml`

#### 3.3: Apply changes

```bash
# Plan to verify changes
terraform plan

# Apply
terraform apply
```

### Phase 4: Verify Migration

Test all endpoints to ensure they work:

```bash
# Health endpoint (managed by runstreak-common)
curl https://<api-gateway-url>/dev/health

# Sync endpoint (managed by myrunstreak.com)
curl -X POST -H "x-api-key: <api-key>" https://<api-gateway-url>/dev/sync

# Stats endpoint (managed by myrunstreak.com)
curl https://<api-gateway-url>/dev/stats/streak
```

## Rollback

If issues occur:

1. **Revert myrunstreak.com** to use the original api_gateway module
2. **Re-import** resources into myrunstreak.com state
3. **Delete** SSM parameters from runstreak-common

```bash
# Delete SSM parameters
aws ssm delete-parameters --names \
  "/runstreak/shared/dev/api-gateway-id" \
  "/runstreak/shared/dev/api-gateway-arn" \
  "/runstreak/shared/dev/api-gateway-execution-arn" \
  "/runstreak/shared/dev/api-gateway-root-resource-id" \
  "/runstreak/shared/dev/api-gateway-stage-name" \
  "/runstreak/shared/dev/api-gateway-invoke-url" \
  "/runstreak/shared/dev/api-gateway-usage-plan-id" \
  "/runstreak/shared/dev/api-gateway-api-key-id" \
  "/runstreak/shared/dev/api-gateway-cloudwatch-role-arn"
```

## Architecture After Migration

```
┌─────────────────────────┐      ┌─────────────────────────┐
│   runstreak-common      │      │    myrunstreak.com      │
│   (Terraform state A)   │      │   (Terraform state B)   │
├─────────────────────────┤      ├─────────────────────────┤
│ aws_api_gateway_rest_api│      │ Routes:                 │
│ aws_api_gateway_stage   │      │ - /sync                 │
│ aws_cloudwatch_log_group│      │ - /stats/{proxy+}       │
│ aws_api_gateway_api_key │      │ - /runs, /runs/{proxy+} │
│ aws_api_gateway_usage_  │      │ - /sync-user            │
│   plan                  │      │ - /auth/*               │
│ /health endpoint        │      │                         │
│                         │      │ Lambda integrations     │
│ SSM Parameters ─────────────────>                        │
└─────────────────────────┘      └─────────────────────────┘
```

## Deployment Order (Ongoing)

After migration, always deploy in this order:

1. **runstreak-common first** - Updates base API Gateway, SSM params
2. **myrunstreak.com second** - Creates/updates routes

If deploying both repos, wait for runstreak-common to complete before deploying myrunstreak.com.
