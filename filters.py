def posterize_filter(frame_resized, levels=4):
    """
    Reduces the number of color levels to create a posterized effect.
    """
    factor = 256 // levels
    posterized = (frame_resized // factor) * factor
    return posterized

