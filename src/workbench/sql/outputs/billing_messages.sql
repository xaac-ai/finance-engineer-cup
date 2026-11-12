SELECT message_id, strftime(sent_at, '%Y-%m-%dT%H:%M:%S%z') AS sent_at, sender, recipient, subject, body
FROM billing_messages ORDER BY message_id
