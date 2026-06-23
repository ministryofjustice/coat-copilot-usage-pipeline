# COAT Copilot Usage Pipeline — AI Credits Extraction

[![Ministry of Justice Repository Compliance Badge](https://github-community.service.justice.gov.uk/repository-standards/api/analytical-platform-airflow-python-template/badge)](https://github-community.service.justice.gov.uk/repository-standards/analytical-platform-airflow-python-template)

This repository contains a Python pipeline that runs as a container on the
Analytical Platform's [Airflow infrastructure](https://github.com/ministryofjustice/analytical-platform-airflow).
It derives per-user GitHub Copilot AI-credit billing data from the daily
`users-1-day` Copilot usage-metrics report, replacing the rate-limited per-user
billing API loop. Since 2026-06-19 the report carries a per-user
`ai_credits_used` field, so no per-user API calls are needed.

## What it does

1. Reads the day's `users-1-day` report files (NDJSON, many partition files)
   from S3.
2. Validates the `ai_credits_used` field is present (reports predate 2026-06-19
   otherwise).
3. Filters users with `ai_credits_used > 0` and builds one billing row per user.
4. Writes a single consolidated Parquet file per day to S3 (queryable in Athena),
   avoiding the small-files problem.

## Output schema (one row per user)

| column | description |
|---|---|
| `year`, `month`, `day` | report date parts |
| `enterprise` | billing enterprise name |
| `user` | Copilot user login |
| `product`, `sku`, `model`, `unit_type` | billing constants (Copilot AI Credits) |
| `price_per_unit` | flat AI-credits price (default 0.01) |
| `gross_quantity` | `ai_credits_used` |
| `gross_amount` | `gross_quantity * price_per_unit` |

## Configuration (environment variables)

| variable | default | description |
|---|---|---|
| `MODE` | `dev` | `dev` / `prod` dataset separation |
| `REPORT_DAY` | yesterday (UTC) | target day, `YYYY-MM-DD` |
| `ENTERPRISE` | `Ministry of Justice (UK)` | billing enterprise name |
| `PRICE_PER_UNIT` | `0.01` | flat AI-credits price |
| `INPUT_BUCKET` / `INPUT_PREFIX` | see `src/config.py` | report source location |
| `OUTPUT_BUCKET` / `OUTPUT_PREFIX` | see `src/config.py` | Parquet output location |

> S3 bucket/prefix defaults in `src/config.py` are placeholders until the real
> paths are confirmed; override them via the environment variables above.

---

## Template setup notes

This repository was created from the Analytical Platform Airflow Python template.

## Included Files

The repository comes with the following preset files:

- GitHub Actions workflows
  - Dependency review (if your repository is public) (`.github/workflows/dependency-review.yml`)
  - Container release to Analytical Platform's ECR (`.github/workflows/release-container.yml`)
  - Container scan with Trivy (`.github/workflows/scan-container.yml`)
  - Container structure test (`.github/workflows/test-container.yml`)
- CODEOWNERS
- Dependabot configuration
- Dockerfile
- MIT License

## Setup Instructions

Once you've created your repository using this template, ensure the following steps:

### Update README

Edit this README.md file to document your project accurately. Take the time to create a clear, engaging, and informative README.md file. Include information like what your project does, how to install and run it, how to contribute, and any other pertinent details.

### Update repository description

After you've created your repository, GitHub provides a brief description field that appears on the top of your repository's main page. This is a summary that gives visitors quick insight into the project. Using this field to provide a succinct overview of your repository is highly recommended.

This description and your README.md will be one of the first things people see when they visit your repository. It's a good place to make a strong, concise first impression. Remember, this is often visible in search results on GitHub and search engines, so it's also an opportunity to help people discover your project.

### Grant Team Permissions

Assign permissions to the appropriate Ministry of Justice teams. Ensure at least one team is granted Admin permissions. Whenever possible, assign permissions to teams rather than individual users.

### Read about the GitHub repository standards

Familiarise yourself with the Ministry of Justice GitHub Repository Standards. These standards ensure consistency, maintainability, and best practices across all our repositories.

You can find the standards [here](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/mojrepostandards.html).

Please read and understand these standards thoroughly and enable them when you feel comfortable.

### Modify the GitHub Standards Badge

Once you've ensured that all the [GitHub Repository Standards](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/mojrepostandards.html) have been applied to your repository, it's time to update the Ministry of Justice (MoJ) Compliance Badge located in the README file.

The badge demonstrates that your repository is compliant with MoJ's standards. Please follow these [instructions](https://user-guide.operations-engineering.service.justice.gov.uk/documentation/information/add-repo-badge.html) to modify the badge URL to reflect the status of your repository correctly.

**Please note** the badge will not function correctly if your repository is internal or private. In this case, you may remove the badge from your README.

### Manage Outside Collaborators

To add an Outside Collaborator to the repository, follow the guidelines detailed [here](https://github.com/ministryofjustice/github-collaborators).

### Update CODEOWNERS

(Optional) Modify the CODEOWNERS file to specify the teams or users authorized to approve pull requests.

### Configure Dependabot

Adapt the dependabot.yml file to match your project's [dependency manager](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#package-ecosystem) and to enable [automated pull requests for package updates](https://docs.github.com/en/code-security/supply-chain-security).

### Dependency Review

If your repository is private with no GitHub Advanced Security license, remove the `.github/workflows/dependency-review.yml` file.
