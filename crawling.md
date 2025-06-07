# Storybook Crawler Guide

## Key Structure

The Storybook site has the following key elements for crawling:

1. **Navigation Tree**
   - Located in `div#storybook-explorer-tree`
   - Contains links to all documentation and story pages
   - Links have `href` attributes starting with `/docs/` or `/story/`

2. **Content Display**
   - Main content is rendered inside an iframe 
   - IFrame ID: `storybook-preview-iframe`
   - Navigating any link in the tree updates this iframe's content

## Crawling Strategy

To effectively crawl this site:

1. Find all links in `#storybook-explorer-tree`
2. Navigate to each link sequentially
3. After each navigation:
   - Wait for the iframe to load
   - Extract its updated content
4. Capture metadata from main page as well

## Important Notes

- The iframe content must be explicitly extracted after each navigation
- Some links may point to groups rather than individual components
- Proper error handling is required when extracting iframe content
- Maintain original navigation order while processing links
## Additional Details

- **Search Functionality**
  - Search field is available in `input#storybook-explorer-searchfield`
  - Can be used to filter links dynamically
  - May require special handling if crawling filtered results

- **Component Types**
  - Docs pages (`/docs/`) provide textual descriptions
  - Story pages (`/story/`) show interactive component examples
  - Both types may contain important metadata in iframe content

- **Loading Indicators**
  - Main page uses `div#preview-loader` as loading indicator
  - Ensure this has disappeared before extracting iframe content

- **Dynamic Content**
  - Some components may have dynamic behavior or interactions
  - Consider waiting for idle state after navigation

- **Error Handling**
  - Links may lead to broken or missing content
  - Implement robust error handling for failed navigations

- **Crawling Depth**
  - Submenus are collapsible via buttons with `aria-controls`
  - May need to expand submenus programmatically to access all links