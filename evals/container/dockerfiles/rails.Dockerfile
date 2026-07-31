FROM ruby:3.3-slim
RUN apt-get update -qq && apt-get install -y nodejs postgresql-client build-essential libpq-dev
WORKDIR /app
COPY Gemfile Gemfile.lock ./
RUN bundle install
COPY . .
ENV PORT=3000 RAILS_ENV=production RAILS_LOG_TO_STDOUT=enabled RAILS_SERVE_STATIC_FILES=enabled SECRET_KEY_BASE=eval_secret_key_base_not_for_production
EXPOSE $PORT
CMD bundle exec puma -t 2:2 -p $PORT -e $RAILS_ENV
