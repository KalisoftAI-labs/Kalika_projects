# Technical Discussion Points

## 1. Migration from EC2 to Cloud Run
- Plan the migration of the application from the current EC2 instance to Google Cloud Run.
- Identify any compatibility issues, deployment changes, and infrastructure requirements.
- Ensure minimal downtime during the migration process.

## 2. RCA (Root Cause Analysis) Dashboard
- Discuss the implementation of an RCA dashboard for tracking incidents and failures.
- The dashboard should provide historical data, root causes, resolutions, and trends to improve operational visibility.

## 3. Planned Downtime Strategy
- Define the scenarios where application downtime is acceptable.
- Decide the preferred maintenance window for deployments, infrastructure updates, and database migrations.
- Establish a communication plan for notifying users before scheduled downtime.

## 4. Memory Cleanup and Maintenance
- Review the current memory usage patterns.
- Determine when memory cleanup or service restarts should be performed.
- Explore automated monitoring and cleanup strategies to prevent memory-related issues.

## 5. Secure Storage of cXML Credentials
- Currently, the cXML credentials are hardcoded in the application.
- Move these credentials to a secure secret management solution or environment variables.
- Ensure sensitive information is not stored in the source code repository.

## 6. FastAPI Admin Panel Security
- The current FastAPI admin panel can be accessed by anyone without proper authentication.
- Implement authentication, authorization, and role-based access control.
- Review additional security measures such as IP restrictions, rate limiting, and secure session management.

## 7. Application Architecture
- The main application is built using Django, while the admin panel is implemented in FastAPI.
- Evaluate whether maintaining two different frameworks is beneficial.
- Discuss possible long-term approaches:
  - Continue with the current hybrid architecture.
  - Rewrite the admin panel in Django.
  - Rebuild the entire application using FastAPI with a React frontend for better consistency and scalability.

## 8. Database Migration Strategy
- The database is currently running inside the EC2 instance.
- Decide how the database should be handled during the migration.
- Consider migrating to a managed database service (e.g., Cloud SQL) instead of hosting it within the application instance.
- Plan database migration, backups, replication, and rollback procedures to minimize downtime and data loss.