"""Initial migration

Revision ID: 174f02d3741b
Revises: 
Create Date: 2025-07-10 14:23:33.045290

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '174f02d3741b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('admin_user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=True),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('images',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ids', sa.String(length=30), nullable=True),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('orders',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_name', sa.String(length=100), nullable=True),
    sa.Column('customer_telephone', sa.String(length=50), nullable=True),
    sa.Column('customer_email', sa.String(length=100), nullable=True),
    sa.Column('dostavka', sa.Boolean(), nullable=True),
    sa.Column('total_price', sa.Float(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('settings_name', sa.String(length=30), nullable=True),
    sa.Column('settings_value', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('catalog_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lot_id', sa.String(length=50), nullable=False),
    sa.Column('color', sa.String(length=50), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('condition', sa.String(length=50), nullable=True),
    sa.Column('sub_condition', sa.String(length=50), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('bulk', sa.Boolean(), nullable=True),
    sa.Column('sale', sa.Boolean(), nullable=True),
    sa.Column('url', sa.String(length=255), nullable=True),
    sa.Column('item_no', sa.String(length=50), nullable=True),
    sa.Column('tier_qty_1', sa.Integer(), nullable=True),
    sa.Column('tier_price_1', sa.Float(), nullable=True),
    sa.Column('tier_qty_2', sa.Integer(), nullable=True),
    sa.Column('tier_price_2', sa.Float(), nullable=True),
    sa.Column('tier_qty_3', sa.Integer(), nullable=True),
    sa.Column('tier_price_3', sa.Float(), nullable=True),
    sa.Column('reserved_for', sa.String(length=100), nullable=True),
    sa.Column('stockroom', sa.String(length=100), nullable=True),
    sa.Column('retain', sa.Boolean(), nullable=True),
    sa.Column('super_lot_id', sa.String(length=50), nullable=True),
    sa.Column('super_lot_qty', sa.Integer(), nullable=True),
    sa.Column('weight', sa.Float(), nullable=True),
    sa.Column('extended_description', sa.Text(), nullable=True),
    sa.Column('date_added', sa.DateTime(), nullable=True),
    sa.Column('date_last_sold', sa.DateTime(), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('order_items',
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('catalog_item_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['catalog_item_id'], ['catalog_items.id'], ),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
    sa.PrimaryKeyConstraint('order_id', 'catalog_item_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('order_items')
    op.drop_table('catalog_items')
    op.drop_table('settings')
    op.drop_table('orders')
    op.drop_table('images')
    op.drop_table('category')
    op.drop_table('admin_user')
    # ### end Alembic commands ###
