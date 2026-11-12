-- title: Every platform invoice line covering the period matches an expected billing document
-- severity: fail
SELECT * FROM platform_documents WHERE expected IS NULL ORDER BY customer_id, service_start
