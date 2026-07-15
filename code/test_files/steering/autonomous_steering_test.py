import matplotlib.pyplot as plt
import numpy as np

def wall_following_control(right_distance, front_distance):
    """
    Improved wall following algorithm that handles both inside and outside turns smoothly.
    
    Args:
        right_distance: Distance to right wall in cm
        front_distance: Distance to front obstacle in cm
    """

    steer = 0.0
    
    if right_distance is not None and front_distance is not None:
        # Target distance from wall (20cm with some tolerance)
        target_distance = 20.0
        target_tolerance = 3.0  # Allow ±3cm tolerance before making corrections
        
        # Much gentler steering gain for smoother control
        base_steer_gain = 0.02  # Reduced from 0.06 for less aggressive steering
        
        # Front obstacle detection threshold
        front_threshold = 35.0  # Slightly increased for earlier turn detection
        
        # Check if we need to turn (front obstacle detected)
        if front_distance < front_threshold:
            # Determine turn direction based on available space
            # For right-wall following, typically turn left when hitting front obstacle
            steer = -0.6  # Moderate left turn, not full lock
            print(f"Front obstacle at {front_distance:.1f}cm - Turning left")
            
        else:
            # Normal wall following mode
            error = right_distance - target_distance
            
            # Only apply steering if outside tolerance zone
            if abs(error) > target_tolerance:
                # Adaptive steering gain based on error magnitude
                if abs(error) > 20.0:
                    # Larger errors need slightly more aggressive correction
                    steer_gain = base_steer_gain * 1.5
                else:
                    steer_gain = base_steer_gain
                
                # Calculate steering command (negative error = too close, steer left)
                steering_command = error * steer_gain
                
                # Apply reasonable limits to prevent jerky movements
                steer = max(-0.8, min(0.8, steering_command))
                
                print(f"Wall distance: {right_distance:.1f}cm, Error: {error:.1f}cm, Steer: {steer:.3f}")
            else:
                # Within tolerance zone - drive straight
                steer = 0.0
                print(f"Wall distance: {right_distance:.1f}cm - Driving straight")
    
    else:
        # Sensor failure - maintain last steering or drive straight
        steer = 0.0
        print("WARNING: Sensor failure - Driving straight")

    return steer

def main():
    right_values = np.arange(1, 51)
    front_values = np.arange(1, 51)
    steer_matrix = np.zeros((len(front_values), len(right_values)))  # Note: rows=front, cols=right

    for i, front in enumerate(front_values):
        for j, right in enumerate(right_values):
            steer = wall_following_control(right, front)
            steer_matrix[i, j] = steer

    plt.figure(figsize=(10, 8))
    im = plt.imshow(steer_matrix, cmap='coolwarm', origin='lower', extent=[1, 50, 1, 50], aspect='auto')
    plt.colorbar(im, label='Steering Command')
    plt.xlabel('Right Distance (cm)')
    plt.ylabel('Front Distance (cm)')
    plt.title('2D Heatmap of Steering Command')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()