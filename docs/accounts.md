# Accounts and automatic research setup

The hosted application now starts with **Sign in** and **Create account**. After registration or sign-in, it automatically prepares a 2,000-row synthetic benchmark and all four calibrated model baselines. The dashboard opens only after setup succeeds. Revisiting the URL with a valid session reloads saved data; signing in from a different browser restores the same account workspace.

## Implementation

Private Blob stores one immutable email-keyed account record with a random UUID, creation timestamp, random salt and scrypt password verifier. A separate UUID index contains only public profile information. No plaintext passwords are retained. Email addresses are normalized; duplicates cannot overwrite accounts. Registration requires 15–128 password characters. Login does not reveal whether an unknown email or incorrect password caused failure.

Sessions use an HMAC-signed `__Host-causallens-account` cookie with a random nonce and issued timestamp. Cookies are Secure, HttpOnly, SameSite=Strict, scoped to `/`, and expire after 30 days. Expiry is enforced on the server. Sign-out records a revocation marker and clears the cookie. Session validation queries authoritative Blob metadata for revocation rather than a delivery URL that could cache a previous missing-object response, so replaying a revoked session is rejected. Session and other API responses are marked private/no-store. Origin checks continue to protect cookie-authenticated requests. Request validation errors for authentication omit submitted values.

Immutable rate-limit slots bound authentication attempts across function instances: 30 attempts per address and 10 per address/email combination in a ten-minute bucket. Address identities are HMAC-hashed before storage. These are research safeguards; they do not replace managed identity, MFA, monitoring or a full abuse-prevention service.

The account UUID scopes dataset/model/report objects. Cookies from the earlier anonymous-browser demo are not login credentials; users must create an account. Anonymous records are not automatically reassigned. Once registered, clearing cookies only signs the user out: signing in again restores account-linked records.

`POST /api/workspace/initialize` uses a private leased lock and a persistent starter reference to avoid duplicate concurrent setup. If a partial attempt already saved a dataset or model, initialization reuses it. Repeated visits and second-browser logins reuse the same saved model version rather than retraining. The browser shows preparation status, bounded retry for concurrent setup, and an explicit retry action on failure.

## Routes

- `POST /api/auth/register`: create an account and set its session cookie.
- `POST /api/auth/login`: verify credentials and rotate to a new session nonce.
- `GET /api/auth/session`: report whether the current session is authenticated.
- `POST /api/auth/logout`: revoke the current session and clear its cookie.
- `POST /api/workspace/initialize`: authenticated, idempotent starter preparation.

Accounts apply to the hosted synthetic demo. Local development retains its key/loopback access mode. The hosted application still rejects private borrower CSV uploads and never executes a lending decision or transaction.

## Limits

This is a research account system. Email verification, password recovery/change, MFA, account deletion, role administration, and automatic retention cleanup are not implemented. The UI states that email verification and recovery are unavailable. There is no outbound email service. Do not treat a registered email as verified identity or use this build for real borrower records.

Verification includes registration, salted hash storage, duplicate-account handling, valid/invalid passwords, account isolation, cross-browser restoration, expired sessions, logout replay rejection, bounded attempts, password-safe validation errors, and starter reuse.
