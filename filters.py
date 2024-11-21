import cv2



def posterize_filter(frame_resized, levels=2):
    """
    Reduces the number of color levels to create a posterized effect.
    """
    factor = 256 // levels
    posterized = (frame_resized // factor) * factor
    return posterized


def thermal_filter(frame_resized):
    """
    Applies a thermal camera effect using a color map.
    """
    gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
    thermal = cv2.applyColorMap(gray, cv2.COLORMAP_JET)
    return thermal
