import React from "react";
import {ViewOverlayDrawer, ViewOverlayDrawerProps} from "../panels/ViewOverlayDrawer";

export type ViewOverlayPanelProps = ViewOverlayDrawerProps;

/**
 * Re-export of ViewOverlayDrawer for backwards-compatible imports.
 */
export const ViewOverlayPanel: React.FC<ViewOverlayPanelProps> = (props) => {
  return <ViewOverlayDrawer {...props} />;
};
