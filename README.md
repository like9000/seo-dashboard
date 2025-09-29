# SEO Dashboard

This document explains how to prepare the environment, configure Supabase, and deploy the SEO Dashboard.

## Prerequisites

Make sure the following tools and accounts are available before you start:

- **Node.js 18.x or later** – required by Next.js and Supabase client libraries.
- **pnpm 8.x** – package manager used for installing dependencies. Install it globally with `corepack enable` or `npm install -g pnpm`.
- **Git** – for cloning the repository and interacting with GitHub.
- **Supabase account** – hosts the application database and authentication.
- **Vercel account** – hosts the production Next.js application.
- **Google Cloud project** – provides OAuth credentials for the robot account used by the dashboard.

Optional, but recommended:

- **Supabase CLI** – simplifies running migrations and managing your local Supabase instance.
- **Vercel CLI** – helps with local previews of the deployed environment.

## Environment variables

Copy the example environment file and fill it with the values that match your project:

```bash
cp .env.example .env.local
```

Update the variables as follows:

- `NEXT_PUBLIC_SUPABASE_URL` – URL of your Supabase project (Project Settings → API → Project URL).
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` – public anon key for client-side requests (Project Settings → API → anon public).
- `SUPABASE_SERVICE_ROLE_KEY` – service role key used only on the server. Keep this secret.
- `SUPABASE_JWT_SECRET` – JWT secret from Supabase Authentication settings.
- `SUPABASE_DB_PASSWORD` – database password from Project Settings → Database.
- `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET` – OAuth credentials generated in Google Cloud.
- `GOOGLE_OAUTH_ROBOT_REFRESH_TOKEN` – refresh token for the robot account generated during OAuth consent.
- `GOOGLE_OAUTH_ROBOT_CLIENT_EMAIL` – client email for the robot/service account that performs automated actions.
- `NEXTAUTH_URL` – URL used by NextAuth (`http://localhost:3000` for local development).
- `NEXTAUTH_SECRET` – random 32+ character string for securing NextAuth sessions.
- `VERCEL_ENV` – set to `development`, `preview`, or `production` depending on the environment.

## Supabase project setup

1. **Create a project** in Supabase and wait until the database is provisioned.
2. **Apply the database schema**:
   - If you are using the Supabase CLI, run `supabase login`, `supabase link --project-ref <project-ref>`, and `supabase db push` from the repository root.
   - Alternatively, open the Supabase Dashboard → SQL Editor and run the SQL schema that ships with the project (for example, import `supabase/schema.sql` if present).
3. **Retrieve the keys** needed for `.env.local`:
   - Go to Project Settings → API and copy the Project URL, anon public key, and service role key.
   - Go to Authentication → Settings to copy the JWT secret.
   - Go to Project Settings → Database to copy the database password and connection string.

## Local development

1. Install dependencies:
   ```bash
   pnpm install
   ```
2. Start the development server:
   ```bash
   pnpm dev
   ```
3. The application is available at [http://localhost:3000](http://localhost:3000). Changes are automatically reloaded.

## Google OAuth (robot account)

1. In the Google Cloud Console, create an OAuth consent screen (Internal or External depending on your needs).
2. Create OAuth 2.0 credentials of type **Web application**.
3. Add the following authorized redirect URIs:
   - `http://localhost:3000/api/auth/callback/google`
   - `https://<your-vercel-domain>/api/auth/callback/google`
4. Download the credentials or copy the generated **Client ID** and **Client Secret**.
5. Generate a refresh token for the robot account by completing the OAuth flow once with offline access (for example, via the Google OAuth Playground) and store it in `GOOGLE_OAUTH_ROBOT_REFRESH_TOKEN`.
6. If a separate service account is used for API access, note its client email and keep the JSON key securely stored.

## Deploying to Vercel

1. Push your repository to GitHub if it is not already there.
2. In Vercel, create a new project and import the GitHub repository.
3. During the import flow, add all environment variables from `.env.local` into Vercel (Settings → Environment Variables). Set them for the `Production`, `Preview`, and `Development` environments as needed.
4. Trigger the first deployment. Vercel will install dependencies with pnpm and build the Next.js app automatically.
5. After deployment, verify that Supabase and Google OAuth integrations work by signing in via the production URL.

## GitHub Secrets and workflow configuration

1. Navigate to **Settings → Secrets and variables → Actions** in your GitHub repository.
2. Add the following secrets so GitHub Actions workflows can build and deploy:

   | Secret name | Purpose |
   |-------------|---------|
   | `VERCEL_TOKEN` | Token generated from the Vercel dashboard for CI deployments. |
   | `VERCEL_ORG_ID` | Your Vercel organization ID (available on the account settings page). |
   | `VERCEL_PROJECT_ID` | The Vercel project ID for the SEO Dashboard. |
   | `SUPABASE_SERVICE_ROLE_KEY` | Needed for running server-side Supabase tasks during CI. |
   | `SUPABASE_DB_PASSWORD` | Allows migrations or tests to connect to the database. |
   | `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Required for E2E tests that exercise Google OAuth. |
   | `GOOGLE_OAUTH_ROBOT_REFRESH_TOKEN` | Enables automated tasks that require a logged-in Google robot account. |
   | `NEXTAUTH_SECRET` | Ensures NextAuth can encrypt cookies during CI runs. |

3. If your workflows rely on other integrations (Analytics, webhooks, etc.), add those secrets as needed.

## Verifying GitHub Actions jobs

- On every push or pull request, open the **Actions** tab in GitHub to confirm that the configured workflows (for example, lint, test, or deploy) have succeeded.
- For quick feedback locally, run the same commands defined in the workflow (commonly `pnpm lint`, `pnpm test`, and `pnpm build`). This helps catch issues before pushing.
- If you have [Act](https://github.com/nektos/act) installed, you can run `act` to execute the workflows locally for additional verification.

With these steps you can develop locally, keep environment variables in sync, and deploy the SEO Dashboard to production with confidence.
