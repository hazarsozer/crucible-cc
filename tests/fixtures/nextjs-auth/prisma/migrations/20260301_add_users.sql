-- Migration: add users + sessions
-- Generated 2026-03-01

CREATE TABLE "User" (
  "id"            UUID         NOT NULL DEFAULT gen_random_uuid(),
  "email"         TEXT         NOT NULL,
  "password_hash" TEXT         NOT NULL,
  "created_at"    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  "updated_at"    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT "User_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "User_email_unique" UNIQUE ("email")
);

CREATE TABLE "Session" (
  "id"         UUID         NOT NULL DEFAULT gen_random_uuid(),
  "user_id"    UUID         NOT NULL,
  "token"      TEXT         NOT NULL,
  "expires_at" TIMESTAMPTZ  NOT NULL,
  "created_at" TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT "Session_pkey" PRIMARY KEY ("id"),
  CONSTRAINT "Session_token_unique" UNIQUE ("token"),
  CONSTRAINT "Session_user_id_fkey"
    FOREIGN KEY ("user_id") REFERENCES "User"("id") ON DELETE CASCADE
);

-- Note: NO index on User.email despite UNIQUE constraint creating one implicitly.
-- Note: NO index on Session.user_id despite the FK — common gap, queries by user_id will scan.
