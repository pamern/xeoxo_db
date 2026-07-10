BEGIN;

ALTER TABLE customization.measurement_appointment
ADD COLUMN IF NOT EXISTS appointment_code VARCHAR(32),
ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200),
ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(20),
ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255);

UPDATE customization.measurement_appointment
SET appointment_code = CONCAT('APT', LPAD(appointment_id::TEXT, 8, '0'))
WHERE appointment_code IS NULL;

ALTER TABLE customization.measurement_appointment
ALTER COLUMN appointment_code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_measurement_appointment_code
ON customization.measurement_appointment (appointment_code);

CREATE INDEX IF NOT EXISTS idx_measurement_appointment_contact_phone
ON customization.measurement_appointment (contact_phone);

CREATE INDEX IF NOT EXISTS idx_measurement_appointment_contact_email
ON customization.measurement_appointment (contact_email);

COMMIT;
