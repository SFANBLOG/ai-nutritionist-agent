-- ============================================
-- AI 营养师 Agent 数据库初始化脚本(MySQL 8.0)
-- 使用方式: mysql -u root -p < sql/init.sql
-- 说明: 项目默认使用 SQLite 开箱即用;切换到 MySQL 时执行本脚本
-- ============================================

CREATE DATABASE IF NOT EXISTS ai_nutritionist
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE ai_nutritionist;

-- 按外键依赖倒序删除
DROP TABLE IF EXISTS dishes;
DROP TABLE IF EXISTS meals;
DROP TABLE IF EXISTS daily_menus;
DROP TABLE IF EXISTS recipes;
DROP TABLE IF EXISTS taste_preferences;
DROP TABLE IF EXISTS health_reports;
DROP TABLE IF EXISTS users;

-- 用户表
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(100) NOT NULL UNIQUE COMMENT '邮箱',
    hashed_password VARCHAR(255) NOT NULL COMMENT '密码哈希',
    full_name VARCHAR(100) COMMENT '真实姓名',
    phone VARCHAR(20) COMMENT '手机号',
    age INT COMMENT '年龄',
    gender VARCHAR(10) COMMENT '性别: male/female/other',
    height DECIMAL(5,2) COMMENT '身高(cm)',
    weight DECIMAL(5,2) COMMENT '体重(kg)',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    is_superuser BOOLEAN DEFAULT FALSE COMMENT '是否管理员',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_email (email),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 健康报告表
CREATE TABLE health_reports (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL COMMENT '用户ID',
    report_name VARCHAR(200) NOT NULL COMMENT '报告名称',
    report_content TEXT COMMENT '报告原始内容',
    analysis_result JSON COMMENT 'AI 分析结果',
    blood_glucose DECIMAL(6,2) COMMENT '血糖值(mmol/L)',
    blood_pressure_systolic INT COMMENT '收缩压(mmHg)',
    blood_pressure_diastolic INT COMMENT '舒张压(mmHg)',
    uric_acid DECIMAL(8,2) COMMENT '尿酸值(μmol/L)',
    cholesterol DECIMAL(6,2) COMMENT '总胆固醇(mmol/L)',
    triglycerides DECIMAL(6,2) COMMENT '甘油三酯(mmol/L)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='健康报告表';

-- 口味偏好表
CREATE TABLE taste_preferences (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL COMMENT '用户ID',
    preference_type VARCHAR(50) NOT NULL COMMENT '偏好类型: favorite_food/disliked_food/cuisine/allergy/goal',
    preference_value VARCHAR(200) NOT NULL COMMENT '偏好值',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='口味偏好表';

-- 食谱表
CREATE TABLE recipes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL COMMENT '用户ID',
    health_report_id INT COMMENT '关联健康报告ID',
    name VARCHAR(200) NOT NULL COMMENT '食谱名称',
    description TEXT COMMENT '食谱描述',
    nutrition_info JSON COMMENT '营养信息(健康分析/营养方案/审核结果/Agent日志等摘要)',
    total_calories INT DEFAULT 0 COMMENT '多日累计总热量(kcal)',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: draft/pending_review/active/revision_requested/archived',
    days INT DEFAULT 1 COMMENT '方案覆盖天数',
    start_date DATE COMMENT '方案起始日期',
    cycle_type VARCHAR(20) DEFAULT 'custom' COMMENT '周期类型: week/month/custom',
    cycle_label VARCHAR(40) COMMENT '周期标签,如 一周/一个月/自定义 N 天',
    review_status VARCHAR(20) DEFAULT 'pending' COMMENT '审核闸门状态: pending/approved/revision_requested',
    review_decision TEXT COMMENT '人工确认意见/结论',
    reviewed_by VARCHAR(50) COMMENT '确认人(用户名)',
    reviewed_at TIMESTAMP NULL COMMENT '确认时间',
    revision_count INT DEFAULT 0 COMMENT '人工请求修订次数',
    human_notes TEXT COMMENT '最近一次人工修订意见',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (health_report_id) REFERENCES health_reports(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='食谱表';

-- 每日菜单表
CREATE TABLE daily_menus (
    id INT PRIMARY KEY AUTO_INCREMENT,
    recipe_id INT NOT NULL COMMENT '所属食谱计划ID',
    user_id INT NOT NULL COMMENT '用户ID',
    menu_date DATE NOT NULL COMMENT '菜单日期',
    total_calories INT DEFAULT 0 COMMENT '总热量(kcal)',
    total_protein DECIMAL(6,2) DEFAULT 0 COMMENT '总蛋白质(g)',
    total_carbohydrate DECIMAL(6,2) DEFAULT 0 COMMENT '总碳水化合物(g)',
    total_fat DECIMAL(6,2) DEFAULT 0 COMMENT '总脂肪(g)',
    notes TEXT COMMENT '当日备注/饮食建议(JSON 或文本)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_recipe_date (recipe_id, menu_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日菜单表';

-- 餐次表
CREATE TABLE meals (
    id INT PRIMARY KEY AUTO_INCREMENT,
    menu_id INT NOT NULL COMMENT '菜单ID',
    meal_type VARCHAR(20) NOT NULL COMMENT '餐次类型: breakfast/lunch/dinner/snack',
    target_calories INT DEFAULT 0 COMMENT '目标热量(kcal)',
    actual_calories INT DEFAULT 0 COMMENT '实际热量(kcal)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (menu_id) REFERENCES daily_menus(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='餐次表';

-- 菜品表
CREATE TABLE dishes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    meal_id INT NOT NULL COMMENT '餐次ID',
    name VARCHAR(200) NOT NULL COMMENT '菜品名称',
    description TEXT COMMENT '菜品描述',
    ingredients TEXT COMMENT '食材清单',
    cooking_method TEXT COMMENT '烹饪方法',
    calories INT DEFAULT 0 COMMENT '热量(kcal)',
    protein DECIMAL(6,2) DEFAULT 0 COMMENT '蛋白质(g)',
    carbohydrate DECIMAL(6,2) DEFAULT 0 COMMENT '碳水化合物(g)',
    fat DECIMAL(6,2) DEFAULT 0 COMMENT '脂肪(g)',
    fiber DECIMAL(6,2) DEFAULT 0 COMMENT '膳食纤维(g)',
    tips TEXT COMMENT '健康提示',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品表';

-- 初始管理员用户(用户名: admin / 密码: admin123)
-- 密码哈希由 bcrypt 生成,首次启动时后端也会自动补建
INSERT INTO users (username, email, hashed_password, full_name, is_superuser)
VALUES
('admin', 'admin@ainutritionist.com',
 '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
 '系统管理员', TRUE);
