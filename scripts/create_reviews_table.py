import mysql.connector
import os

def create_reviews_table():
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='root',
            database='furniture_shop'
        )
        cursor = connection.cursor()
        
        # Create reviews table
        query = """
        CREATE TABLE IF NOT EXISTS reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            product_id INT NOT NULL,
            rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """
        cursor.execute(query)
        connection.commit()
        print("Reviews table created or already exists.")
        
        cursor.close()
        connection.close()
    except mysql.connector.Error as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_reviews_table()
