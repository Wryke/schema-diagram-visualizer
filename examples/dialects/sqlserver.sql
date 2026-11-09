/****** Written by hand in the format SQL Server Management Studio scripts produce. ******/
USE [Store]
GO
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
CREATE TABLE [dbo].[Customers](
	[CustomerID] [int] IDENTITY(1,1) NOT NULL,
	[Name] [nvarchar](100) NOT NULL,
	[Notes] [nvarchar](max) NULL,
	[key] [varchar](max) NULL,
	[index] [int] NULL,
	[Greeting] [nvarchar](20) NOT NULL DEFAULT (N'it''s me'),
	[Added] [datetime2](7) NOT NULL CONSTRAINT [DF_Customers_Added] DEFAULT (getdate()),
 CONSTRAINT [PK_Customers] PRIMARY KEY CLUSTERED
(
	[CustomerID] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF) ON [PRIMARY],
 CONSTRAINT [UQ_Customers_Name] UNIQUE NONCLUSTERED
(
	[Name] ASC
)WITH (PAD_INDEX = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO
CREATE TABLE [sales].[Order Header](
	[OrderID] [int] IDENTITY(1,1) NOT NULL,
	[CustomerID] [int] NOT NULL,
	[Total] [decimal](10, 2) NULL,
	[Doubled] AS ([Total]*(2)),
	[Status] [varchar](10) NOT NULL,
 CONSTRAINT [PK_Order] PRIMARY KEY CLUSTERED ([OrderID] ASC) ON [PRIMARY]
) ON [PRIMARY]
GO
CREATE TABLE [sales].[OrderLine](
	[OrderID] [int] NOT NULL,
	[LineNo] [int] NOT NULL,
	[ParentLine] [int] NULL,
 CONSTRAINT [PK_OrderLine] PRIMARY KEY CLUSTERED ([OrderID] ASC, [LineNo] ASC) ON [PRIMARY]
) ON [PRIMARY]
GO
ALTER TABLE [sales].[Order Header] ADD CONSTRAINT [DF_Status] DEFAULT ('new') FOR [Status]
GO
ALTER TABLE [sales].[Order Header] WITH CHECK ADD CONSTRAINT [FK_Order_Customer] FOREIGN KEY([CustomerID])
REFERENCES [dbo].[Customers] ([CustomerID])
ON DELETE CASCADE
GO
ALTER TABLE [sales].[Order Header] CHECK CONSTRAINT [FK_Order_Customer]
GO
ALTER TABLE [sales].[OrderLine] WITH NOCHECK ADD CONSTRAINT [FK_Line_Order] FOREIGN KEY([OrderID])
REFERENCES [sales].[Order Header] ([OrderID])
NOT FOR REPLICATION
GO
ALTER TABLE [sales].[Order Header] WITH CHECK ADD CONSTRAINT [CK_Total] CHECK (([Total]>=(0)))
GO
CREATE PROCEDURE [dbo].[GetCustomers]
AS
BEGIN
	SELECT 'it''s here'; -- a semicolon, then no more until GO
	SELECT @@ROWCOUNT
END
GO
