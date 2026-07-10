-- =========================================================
-- PROJECT: XEOXO WEB
-- FILE: 03_create_business_tables.sql
-- PURPOSE: Tạo các bảng ngoài schema catalog theo database specification
-- NOTE: Mục TRANSACTION trong docs hiện chưa có đặc tả cột cụ thể nên chưa tạo bảng.
-- =========================================================

BEGIN;

-- =====================================================
-- IAM SCHEMA
-- =====================================================

CREATE TABLE iam.account (
    account_id UUID PRIMARY KEY
        REFERENCES auth.users(id)
        ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_account_role
        CHECK (role IN ('CUSTOMER', 'STAFF', 'ADMIN'))
);

CREATE TABLE iam.loyalty_tier (
    loyalty_tier_id VARCHAR(20) PRIMARY KEY,
    tier_name VARCHAR(100) NOT NULL,
    min_accumulated_amount NUMERIC(14, 2) NOT NULL,
    maintain_amount NUMERIC(14, 2) NOT NULL,
    birthday_voucher_value NUMERIC(14, 2),
    free_shipping_quota SMALLINT NOT NULL,
    free_tailor_quota SMALLINT NOT NULL,
    special_gift VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_loyalty_tier_id
        CHECK (loyalty_tier_id IN ('SILVER', 'GOLD', 'DIAMOND', 'MVG'))
);

CREATE TABLE iam.province (
    province_id SERIAL PRIMARY KEY,
    province_name VARCHAR(150) NOT NULL,
    region VARCHAR(30) NOT NULL,
    ward TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_province_region
        CHECK (region IN ('Miền Bắc', 'Miền Trung', 'Miền Nam'))
);

CREATE TABLE iam.customer (
    customer_id BIGSERIAL PRIMARY KEY,
    account_id UUID UNIQUE
        REFERENCES iam.account(account_id)
        ON DELETE SET NULL,
    customer_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(20),
    gender VARCHAR(20),
    birthday DATE,
    customer_type VARCHAR(20) NOT NULL,
    tier_id VARCHAR(20)
        REFERENCES iam.loyalty_tier(loyalty_tier_id)
        ON DELETE SET NULL,
    total_spent NUMERIC(14, 2) NOT NULL DEFAULT 0,
    spent_in_year NUMERIC(14, 2) NOT NULL DEFAULT 0,
    last_tier_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_customer_type
        CHECK (customer_type IN ('MEMBER', 'GUEST'))
);

CREATE TABLE iam.address (
    address_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES iam.customer(customer_id)
        ON DELETE CASCADE,
    recipient_name VARCHAR(255) NOT NULL,
    recipient_phone VARCHAR(20) NOT NULL,
    province_id INT NOT NULL
        REFERENCES iam.province(province_id)
        ON DELETE RESTRICT,
    district_name VARCHAR(255) NOT NULL,
    address_detail TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE iam.branch (
    branch_id SERIAL PRIMARY KEY,
    branch_name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    phone VARCHAR(20) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    manager_id INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE iam.staff (
    staff_id SERIAL PRIMARY KEY,
    account_id UUID NOT NULL
        REFERENCES iam.account(account_id)
        ON DELETE RESTRICT,
    branch_id INT NOT NULL
        REFERENCES iam.branch(branch_id)
        ON DELETE RESTRICT,
    staff_name VARCHAR(255) NOT NULL,
    position VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

ALTER TABLE iam.branch
    ADD CONSTRAINT fk_branch_manager
    FOREIGN KEY (manager_id)
    REFERENCES iam.staff(staff_id)
    ON DELETE SET NULL;

CREATE TABLE iam.loyalty_reward (
    reward_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES iam.customer(customer_id)
        ON DELETE CASCADE,
    loyalty_tier_id VARCHAR(20) NOT NULL
        REFERENCES iam.loyalty_tier(loyalty_tier_id)
        ON DELETE RESTRICT,
    reward_type VARCHAR(30) NOT NULL,
    reward_name VARCHAR(255) NOT NULL,
    voucher_code VARCHAR(100) UNIQUE,
    reward_value NUMERIC(14, 2),
    issued_at TIMESTAMPTZ NOT NULL,
    expired_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_loyalty_reward_type
        CHECK (
            reward_type IN (
                'BIRTHDAY_VOUCHER',
                'TIER_VOUCHER',
                'FREE_SHIPPING',
                'FREE_TAILOR',
                'SPECIAL_GIFT'
            )
        ),
    CONSTRAINT chk_loyalty_reward_status
        CHECK (status IN ('AVAILABLE', 'USED', 'EXPIRED', 'CANCELLED'))
);

-- =====================================================
-- CUSTOMIZATION SCHEMA
-- =====================================================

CREATE TABLE customization.measurement_profile (
    measurement_profile_id SERIAL PRIMARY KEY,
    appointment_id INT,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    measured_by INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    note TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    measurement_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS _measurement_profile_customer_active
ON customization.measurement_profile (customer_id)
WHERE is_active = TRUE;

CREATE TABLE customization.customization_request (
    customization_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    component_id INT NOT NULL
        REFERENCES catalog.product_component(component_id)
        ON DELETE RESTRICT,
    measurement_profile_id INT
        REFERENCES customization.measurement_profile(measurement_profile_id)
        ON DELETE SET NULL,
    unit_price NUMERIC(14, 2) NOT NULL,
    surcharge_percent NUMERIC(5, 2) NOT NULL,
    surcharge_amount NUMERIC(14, 2) NOT NULL,
    custom_price NUMERIC(14, 2) NOT NULL,
    measurement_snapshot JSONB,
    customization_status VARCHAR(30) NOT NULL,
    customer_note TEXT,
    staff_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_customization_status
        CHECK (
            customization_status IN (
                'REQUESTED',
                'MEASUREMENT_PENDING',
                'MEASURED',
                'CONFIRMED',
                'IN_PROGRESS',
                'COMPLETED',
                'CANCELLED'
            )
        )
);

CREATE TABLE customization.measurement_appointment (
    appointment_id SERIAL PRIMARY KEY,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    product_line_id INT
        REFERENCES catalog.product_line(product_line_id)
        ON DELETE SET NULL,
    branch_id INT NOT NULL
        REFERENCES iam.branch(branch_id)
        ON DELETE RESTRICT,
    staff_id INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    appointment_status VARCHAR(20) NOT NULL,
    customer_note TEXT,
    staff_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_measurement_appointment_status
        CHECK (appointment_status IN ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')),
    CONSTRAINT chk_measurement_appointment_time
        CHECK (end_time > start_time)
);

ALTER TABLE customization.measurement_profile
    ADD CONSTRAINT fk_measurement_profile_appointment
    FOREIGN KEY (appointment_id)
    REFERENCES customization.measurement_appointment(appointment_id)
    ON DELETE SET NULL;

CREATE TABLE customization.measurement_profile_detail (
    measurement_detail_id SERIAL PRIMARY KEY,
    measurement_profile_id INT NOT NULL
        REFERENCES customization.measurement_profile(measurement_profile_id)
        ON DELETE CASCADE,
    measurement_type_id INT NOT NULL
        REFERENCES catalog.measurement_type(measurement_type_id)
        ON DELETE RESTRICT,
    measurement_value NUMERIC(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- =====================================================
-- SALES SCHEMA
-- =====================================================

CREATE TABLE sales.payment_method (
    method_id SERIAL PRIMARY KEY,
    method_name VARCHAR(100) NOT NULL,
    method_code VARCHAR(30) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_payment_method_code
        CHECK (method_code IN ('COD', 'MOMO', 'VNPAY', 'CARD', 'BANK_TRANSFER'))
);

CREATE TABLE sales.cart (
    cart_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    session_id UUID,
    cart_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_cart_status
        CHECK (cart_status IN ('ACTIVE', 'CHECKOUT', 'ABANDONED'))
);

CREATE TABLE sales.cart_item (
    cart_item_id BIGSERIAL PRIMARY KEY,
    cart_id BIGINT NOT NULL
        REFERENCES sales.cart(cart_id)
        ON DELETE CASCADE,
    variant_id INT
        REFERENCES catalog.product_variant(variant_id)
        ON DELETE RESTRICT,
    customization_id BIGINT
        REFERENCES customization.customization_request(customization_id)
        ON DELETE CASCADE,
    customization_snapshot JSONB,
    item_type VARCHAR(20) NOT NULL,
    quantity INT NOT NULL,
    unit_price NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_cart_item_variant
        UNIQUE (cart_id, variant_id),
    CONSTRAINT uq_cart_item_customization
        UNIQUE (cart_id, customization_id),
    CONSTRAINT chk_cart_item_type
        CHECK (item_type IN ('STANDARD', 'CUSTOMIZED')),
    CONSTRAINT chk_cart_item_quantity
        CHECK (quantity > 0),
    CONSTRAINT chk_cart_item_reference
        CHECK (
            (item_type = 'STANDARD' AND variant_id IS NOT NULL AND customization_id IS NULL)
            OR (item_type = 'CUSTOMIZED' AND variant_id IS NULL AND customization_id IS NOT NULL)
        )
);

CREATE TABLE sales.sales_order (
    order_id BIGSERIAL PRIMARY KEY,
    order_code VARCHAR(50) NOT NULL UNIQUE,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    order_date TIMESTAMPTZ NOT NULL,
    reward_discount_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    shipping_fee NUMERIC(14, 2) NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL,
    order_status VARCHAR(30) NOT NULL,
    payment_status VARCHAR(30) NOT NULL,
    customer_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_sales_order_status
        CHECK (
            order_status IN (
                'PENDING',
                'CONFIRMED',
                'PACKING',
                'SHIPPING',
                'COMPLETED',
                'CANCELLED',
                'RETURNED'
            )
        ),
    CONSTRAINT chk_sales_payment_status
        CHECK (payment_status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED'))
);

CREATE TABLE iam.reward_usage (
    usage_id BIGSERIAL PRIMARY KEY,
    reward_id BIGINT NOT NULL
        REFERENCES iam.loyalty_reward(reward_id)
        ON DELETE CASCADE,
    order_id BIGINT NOT NULL
        REFERENCES sales.sales_order(order_id)
        ON DELETE CASCADE,
    used_amount NUMERIC(14, 2),
    used_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE sales.order_item (
    order_item_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES sales.sales_order(order_id)
        ON DELETE CASCADE,
    variant_id INT
        REFERENCES catalog.product_variant(variant_id)
        ON DELETE SET NULL,
    customization_id BIGINT
        REFERENCES customization.customization_request(customization_id)
        ON DELETE SET NULL,
    customization_snapshot JSONB,
    item_type VARCHAR(20) NOT NULL,
    quantity INT NOT NULL,
    unit_price NUMERIC(14, 2) NOT NULL,
    discount_amount NUMERIC(14, 2) NOT NULL,
    line_total NUMERIC(14, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_order_item_type
        CHECK (item_type IN ('STANDARD', 'CUSTOMIZED')),
    CONSTRAINT chk_order_item_quantity
        CHECK (quantity > 0),
    CONSTRAINT chk_order_item_reference
        CHECK (
            (item_type = 'STANDARD' AND variant_id IS NOT NULL)
            OR (item_type = 'CUSTOMIZED' AND customization_id IS NOT NULL)
        )
);

CREATE OR REPLACE FUNCTION sales.set_cart_item_customization_snapshot()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.item_type = 'CUSTOMIZED' AND NEW.customization_id IS NOT NULL THEN
        IF NEW.customization_snapshot IS NULL THEN
            SELECT cr.measurement_snapshot
            INTO NEW.customization_snapshot
            FROM customization.customization_request AS cr
            WHERE cr.customization_id = NEW.customization_id;
        END IF;
    ELSE
        NEW.customization_snapshot := NULL;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cart_item_set_customization_snapshot
BEFORE INSERT OR UPDATE OF customization_id, customization_snapshot, item_type
ON sales.cart_item
FOR EACH ROW
EXECUTE FUNCTION sales.set_cart_item_customization_snapshot();

CREATE TABLE sales.payment (
    payment_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES sales.sales_order(order_id)
        ON DELETE CASCADE,
    method_id INT NOT NULL
        REFERENCES sales.payment_method(method_id)
        ON DELETE RESTRICT,
    amount NUMERIC(14, 2) NOT NULL,
    payment_status VARCHAR(30) NOT NULL,
    transaction_code VARCHAR(255) NOT NULL UNIQUE,
    paid_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_payment_status
        CHECK (payment_status IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED'))
);

CREATE TABLE sales.return_request (
    return_id SERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES sales.sales_order(order_id)
        ON DELETE CASCADE,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    return_reason TEXT NOT NULL,
    return_status VARCHAR(30) NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    approved_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    handled_by INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_return_request_status
        CHECK (
            return_status IN (
                'REQUESTED',
                'APPROVED',
                'REJECTED',
                'RETURNING',
                'RECEIVED',
                'COMPLETED',
                'CANCELLED'
            )
        )
);

CREATE TABLE sales.refund (
    refund_id SERIAL PRIMARY KEY,
    payment_id BIGINT NOT NULL
        REFERENCES sales.payment(payment_id)
        ON DELETE CASCADE,
    return_id INT
        REFERENCES sales.return_request(return_id)
        ON DELETE SET NULL,
    refund_status VARCHAR(20) NOT NULL,
    transaction_code VARCHAR(255) UNIQUE,
    reason TEXT,
    refunded_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_refund_status
        CHECK (refund_status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED'))
);

CREATE TABLE sales.shipping (
    shipping_id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL
        REFERENCES sales.sales_order(order_id)
        ON DELETE CASCADE,
    address_id BIGINT NOT NULL
        REFERENCES iam.address(address_id)
        ON DELETE RESTRICT,
    shipping_provider VARCHAR(100) NOT NULL,
    tracking_code VARCHAR(100) UNIQUE,
    shipping_status VARCHAR(30) NOT NULL,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE TABLE sales.return_item (
    return_item_id SERIAL PRIMARY KEY,
    return_id INT NOT NULL
        REFERENCES sales.return_request(return_id)
        ON DELETE CASCADE,
    order_item_id BIGINT NOT NULL
        REFERENCES sales.order_item(order_item_id)
        ON DELETE CASCADE,
    return_quantity INT NOT NULL,
    return_amount NUMERIC(14, 2) NOT NULL,
    item_condition VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_return_item_quantity
        CHECK (return_quantity > 0)
);

CREATE TABLE sales.review (
    review_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL
        REFERENCES iam.customer(customer_id)
        ON DELETE CASCADE,
    order_item_id BIGINT NOT NULL UNIQUE
        REFERENCES sales.order_item(order_item_id)
        ON DELETE CASCADE,
    rating SMALLINT NOT NULL,
    review_content TEXT,
    review_status VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_review_rating
        CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT chk_review_status
        CHECK (review_status IN ('HIDDEN', 'DISPLAY'))
);

CREATE TABLE sales.review_media (
    review_id BIGINT NOT NULL
        REFERENCES sales.review(review_id)
        ON DELETE CASCADE,
    media_id BIGINT NOT NULL
        REFERENCES catalog.media(media_id)
        ON DELETE CASCADE,
    display_order SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (review_id, media_id),
    CONSTRAINT chk_review_media_display_order
        CHECK (display_order > 0)
);

-- =====================================================
-- INVENTORY SCHEMA
-- =====================================================

CREATE TABLE inventory.inventory (
    inventory_id SERIAL PRIMARY KEY,
    branch_id INT NOT NULL
        REFERENCES iam.branch(branch_id)
        ON DELETE CASCADE,
    variant_id INT NOT NULL
        REFERENCES catalog.product_variant(variant_id)
        ON DELETE CASCADE,
    quantity INT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT uq_inventory_branch_variant
        UNIQUE (branch_id, variant_id),
    CONSTRAINT chk_inventory_quantity
        CHECK (quantity >= 0)
);

-- =====================================================
-- SUPPORT SCHEMA
-- =====================================================

CREATE TABLE support.chat_conversation (
    conversation_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    guest_session_id UUID,
    assigned_staff_id INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    last_message_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_chat_conversation_channel
        CHECK (channel IN ('WEB', 'MOBILE')),
    CONSTRAINT chk_chat_conversation_status
        CHECK (status IN ('OPEN', 'WAITING', 'CLOSED'))
);

CREATE TABLE support.chat_message (
    message_id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES support.chat_conversation(conversation_id)
        ON DELETE CASCADE,
    sender_type VARCHAR(20) NOT NULL,
    sender_customer_id BIGINT
        REFERENCES iam.customer(customer_id)
        ON DELETE SET NULL,
    sender_staff_id INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    message_type VARCHAR(20) NOT NULL,
    message_content TEXT,
    reply_to_message_id BIGINT
        REFERENCES support.chat_message(message_id)
        ON DELETE SET NULL,
    sent_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_chat_message_sender_type
        CHECK (sender_type IN ('CUSTOMER', 'STAFF')),
    CONSTRAINT chk_chat_message_type
        CHECK (message_type IN ('TEXT', 'IMAGE', 'FILE', 'SYSTEM'))
);

CREATE TABLE support.chat_message_media (
    message_id BIGINT NOT NULL
        REFERENCES support.chat_message(message_id)
        ON DELETE CASCADE,
    media_id BIGINT NOT NULL
        REFERENCES catalog.media(media_id)
        ON DELETE CASCADE,
    display_order SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (message_id, media_id),
    CONSTRAINT chk_chat_message_media_display_order
        CHECK (display_order > 0)
);

CREATE TABLE support.chat_assignment_history (
    assignment_id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL
        REFERENCES support.chat_conversation(conversation_id)
        ON DELETE CASCADE,
    staff_id INT NOT NULL
        REFERENCES iam.staff(staff_id)
        ON DELETE RESTRICT,
    assigned_by INT NOT NULL
        REFERENCES iam.staff(staff_id)
        ON DELETE RESTRICT,
    assigned_at TIMESTAMPTZ NOT NULL,
    unassigned_at TIMESTAMPTZ,
    reason VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE support.chat_message_read (
    message_id BIGINT NOT NULL
        REFERENCES support.chat_message(message_id)
        ON DELETE CASCADE,
    reader_type VARCHAR(20) NOT NULL,
    reader_id BIGINT NOT NULL,
    read_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (message_id, reader_type, reader_id),
    CONSTRAINT chk_chat_message_read_type
        CHECK (reader_type IN ('CUSTOMER', 'STAFF'))
);

CREATE TABLE support.chat_tag (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE support.chat_conversation_tag (
    conversation_id BIGINT NOT NULL
        REFERENCES support.chat_conversation(conversation_id)
        ON DELETE CASCADE,
    tag_id INT NOT NULL
        REFERENCES support.chat_tag(tag_id)
        ON DELETE CASCADE,
    assigned_by INT
        REFERENCES iam.staff(staff_id)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (conversation_id, tag_id)
);

COMMIT;
