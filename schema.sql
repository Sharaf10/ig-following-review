create table if not exists public.ig_following_reviews (
  owner_id text not null,
  username text not null,
  profile_url text not null,
  followed_at bigint,
  status text not null default 'pending' check (status in ('pending', 'keep', 'unfollowed', 'later')),
  updated_at timestamptz not null default now(),
  primary key (owner_id, username)
);

create index if not exists ig_following_reviews_owner_status_idx
  on public.ig_following_reviews (owner_id, status);

create index if not exists ig_following_reviews_owner_followed_idx
  on public.ig_following_reviews (owner_id, followed_at desc);

-- This app uses the Supabase service-role key only on the Streamlit server.
-- Do NOT put the service-role key in client-side JavaScript or commit it to GitHub.
alter table public.ig_following_reviews enable row level security;
