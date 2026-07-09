BEGIN;

-- =========================================================
-- PURPOSE
-- - Tự động cấp loyalty reward khi customer được nâng hạng.
-- - Chỉ cấp khi tier mới có rank cao hơn tier cũ.
-- - Dùng voucher_code nội bộ làm định danh để tránh cấp trùng reward
--   cho cùng customer, cùng tier và cùng reward_type.
--
-- Ghi chú:
-- - `reward_value` của `FREE_SHIPPING` và `FREE_TAILOR` được dùng để lưu quota.
-- - `reward_value` của `BIRTHDAY_VOUCHER` là số tiền voucher.
-- - `reward_value` của `SPECIAL_GIFT` để NULL vì quyền lợi được mô tả bằng text.
-- =========================================================

CREATE OR REPLACE FUNCTION util.loyalty_tier_rank(tier_id VARCHAR)
RETURNS SMALLINT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE UPPER(COALESCE(tier_id, ''))
        WHEN 'SILVER' THEN 1
        WHEN 'GOLD' THEN 2
        WHEN 'DIAMOND' THEN 3
        WHEN 'MVG' THEN 4
        ELSE 0
    END
$$;

COMMENT ON FUNCTION util.loyalty_tier_rank(VARCHAR) IS
'Trả về rank nội bộ của loyalty tier để so sánh việc nâng hạng.';

CREATE OR REPLACE FUNCTION iam.issue_loyalty_rewards_on_tier_upgrade()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, iam, util
AS $$
DECLARE
    current_tier iam.loyalty_tier%ROWTYPE;
    old_rank SMALLINT;
    new_rank SMALLINT;
BEGIN
    IF TG_OP <> 'UPDATE' THEN
        RETURN NEW;
    END IF;

    IF NEW.tier_id IS NULL OR NEW.tier_id IS NOT DISTINCT FROM OLD.tier_id THEN
        RETURN NEW;
    END IF;

    old_rank := util.loyalty_tier_rank(OLD.tier_id);
    new_rank := util.loyalty_tier_rank(NEW.tier_id);

    -- Chỉ phát reward khi customer được nâng lên tier cao hơn.
    IF new_rank <= old_rank THEN
        RETURN NEW;
    END IF;

    SELECT *
    INTO current_tier
    FROM iam.loyalty_tier
    WHERE loyalty_tier_id = NEW.tier_id;

    IF NOT FOUND THEN
        RETURN NEW;
    END IF;

    IF current_tier.birthday_voucher_value IS NOT NULL
       AND current_tier.birthday_voucher_value > 0 THEN
        INSERT INTO iam.loyalty_reward (
            customer_id,
            loyalty_tier_id,
            reward_type,
            reward_name,
            voucher_code,
            reward_value,
            issued_at,
            status
        )
        SELECT
            NEW.customer_id,
            NEW.tier_id,
            'BIRTHDAY_VOUCHER',
            FORMAT('Quà sinh nhật hạng %s', current_tier.tier_name),
            FORMAT('LOYALTY-%s-%s-BDAY', NEW.customer_id, NEW.tier_id),
            current_tier.birthday_voucher_value,
            NOW(),
            'AVAILABLE'
        WHERE NOT EXISTS (
            SELECT 1
            FROM iam.loyalty_reward AS lr
            WHERE lr.voucher_code = FORMAT('LOYALTY-%s-%s-BDAY', NEW.customer_id, NEW.tier_id)
        );
    END IF;

    IF current_tier.free_shipping_quota > 0 THEN
        INSERT INTO iam.loyalty_reward (
            customer_id,
            loyalty_tier_id,
            reward_type,
            reward_name,
            voucher_code,
            reward_value,
            issued_at,
            status
        )
        SELECT
            NEW.customer_id,
            NEW.tier_id,
            'FREE_SHIPPING',
            FORMAT('Miễn phí vận chuyển hạng %s', current_tier.tier_name),
            FORMAT('LOYALTY-%s-%s-FREESHIP', NEW.customer_id, NEW.tier_id),
            current_tier.free_shipping_quota::NUMERIC,
            NOW(),
            'AVAILABLE'
        WHERE NOT EXISTS (
            SELECT 1
            FROM iam.loyalty_reward AS lr
            WHERE lr.voucher_code = FORMAT('LOYALTY-%s-%s-FREESHIP', NEW.customer_id, NEW.tier_id)
        );
    END IF;

    IF current_tier.free_tailor_quota > 0 THEN
        INSERT INTO iam.loyalty_reward (
            customer_id,
            loyalty_tier_id,
            reward_type,
            reward_name,
            voucher_code,
            reward_value,
            issued_at,
            status
        )
        SELECT
            NEW.customer_id,
            NEW.tier_id,
            'FREE_TAILOR',
            FORMAT('Miễn phí may đo hạng %s', current_tier.tier_name),
            FORMAT('LOYALTY-%s-%s-TAILOR', NEW.customer_id, NEW.tier_id),
            current_tier.free_tailor_quota::NUMERIC,
            NOW(),
            'AVAILABLE'
        WHERE NOT EXISTS (
            SELECT 1
            FROM iam.loyalty_reward AS lr
            WHERE lr.voucher_code = FORMAT('LOYALTY-%s-%s-TAILOR', NEW.customer_id, NEW.tier_id)
        );
    END IF;

    IF current_tier.special_gift IS NOT NULL
       AND BTRIM(current_tier.special_gift) <> '' THEN
        INSERT INTO iam.loyalty_reward (
            customer_id,
            loyalty_tier_id,
            reward_type,
            reward_name,
            voucher_code,
            reward_value,
            issued_at,
            status
        )
        SELECT
            NEW.customer_id,
            NEW.tier_id,
            'SPECIAL_GIFT',
            current_tier.special_gift,
            FORMAT('LOYALTY-%s-%s-GIFT', NEW.customer_id, NEW.tier_id),
            NULL,
            NOW(),
            'AVAILABLE'
        WHERE NOT EXISTS (
            SELECT 1
            FROM iam.loyalty_reward AS lr
            WHERE lr.voucher_code = FORMAT('LOYALTY-%s-%s-GIFT', NEW.customer_id, NEW.tier_id)
        );
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION iam.issue_loyalty_rewards_on_tier_upgrade() IS
'Trigger function tự cấp loyalty reward khi customer được nâng hạng.';

DROP TRIGGER IF EXISTS trg_issue_loyalty_rewards_on_tier_upgrade ON iam.customer;

CREATE TRIGGER trg_issue_loyalty_rewards_on_tier_upgrade
AFTER UPDATE OF tier_id
ON iam.customer
FOR EACH ROW
EXECUTE FUNCTION iam.issue_loyalty_rewards_on_tier_upgrade();

COMMIT;
