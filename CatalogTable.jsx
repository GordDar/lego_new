import Box from '@mui/material/Box';
import Grid from '@mui/material/Unstable_Grid2';
import {Button} from "@mui/material";
import {Link, MemoryRouter, Route, Routes, useLocation} from 'react-router-dom';
import PaginationItem from '@mui/material/PaginationItem';
import MenuItem from '@mui/material/MenuItem';
import FormControl from '@mui/material/FormControl';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Select, {SelectChangeEvent} from '@mui/material/Select';

import Pagination from '../Pagination/Pagination';
import {useContext, useEffect, useState} from "react";
import Paper from "@mui/material/Paper";
import Checkbox from '@mui/material/Checkbox';
import {CartContext} from "../../context/CartContext";

export default function CatalogTable({ items }) {
  const { addItem, removeItem, isItemInCart, reloader } = useContext(CartContext);

  const [data, setData] = useState([]);
  const [quantities, setQuantities] = useState({}); // состояние счетчиков

  // Инициализация счетчиков при изменении items
  useEffect(() => {
    const initialQuantities = {};
    items.forEach((product) => {
      initialQuantities[product.id] = 0; // начальное значение счетчика
    });
    setQuantities(initialQuantities);
  }, [items]);


  useEffect(() => {
    const currentData = items.map((product, index) => {
      const quantityCount = quantities[product.id] || 0;

      const handleDecrement = () => {
        if (quantityCount > 0) {
          setQuantities(prev => ({ ...prev, [product.id]: prev[product.id] - 1 }));
        }
      };

      const handleIncrement = () => {
        if (quantityCount < product.quantity) {
          setQuantities(prev => ({ ...prev, [product.id]: prev[product.id] + 1 }));
        }
      };

      return (
        <Paper key={product.id} sx={{
          width: { xs: "auto" },
          height: { xs: "auto" },
          padding: { xs: "5px", md: 0 },
          margin: { xs: "10px auto", md: 0 },
          backgroundColor: (index % 2 === 1) ? "" : "#f2f2f2",
          boxShadow: { md: "none", xs: "0px 4px 5px -2px rgba(0,0,0,0.2),0px 7px 10px 1px rgba(0,0,0,0.14),0px 2px 16px 1px rgba(0,0,0,0.12)" }
        }}>
          <Grid container alignItems="center" spacing={2} sx={{ marginTop: { xs: "15px", md: 'auto' }, marginBottom: "10px" }}>
            <Grid sx={{ display: "flex", alignItems: "center", justifyContent: { xs: "center" } }} xs={6} md={2}>
              <Box component="img" sx={{ height: 90, objectFit: "cover", borderRadius: "10px" }} src={product.imageUrl} alt="" />
            </Grid>
            <Grid xs={6} md={2}>
              {product.condition}
            </Grid>
            <Grid xs={6} md={2}>
              {product.color}
            </Grid>
            <Grid xs={6} md={3}>
              {product.description}
            </Grid>
            <Grid xs={12} md={3}>
              <Stack>
                <Typography>
                  Наличие: {product.quantity}
                </Typography>
                <Typography>
                  Цена: {product.price} {product.currency}
                </Typography>



                {/* Блок с кнопками минус/плюс и счетчиком */}
                <Box sx={{ display: 'flex', alignItems: 'center', marginTop: '8px' }}>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleDecrement}
                  >
                    -
                  </Button>
                  <Typography sx={{ marginX: '8px' }}>{quantityCount}</Typography>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleIncrement}
                  >
                    +
                  </Button>
                </Box>



                {isItemInCart(product.id)
                  ? (
                    <Button className={"accent-button-style"} onClick={() => removeItem(product.id)}>
                      Убрать из корзины
                    </Button>
                  )
                  : (
                    <Button className={"accent-button-style"} onClick={() => addItem(product)}>
                      Добавить в корзину
                    </Button>
                  )
                }
              </Stack>
            </Grid>
          </Grid>
        </Paper>
      );
    });

    if(currentData && currentData.length) {
      setData(currentData);
    } else {
      setData(
        <Box sx={{backgroundColor: "lightgrey", padding: "15px", borderRadius: "5px"}}>
          <strong>
            Нет добавленных товаров
          </strong>
        </Box>
      )
    }
  }, [items, reloader]);

  return (
    <div className="buyouts-table">
      <Box sx={{flexGrow: 1}}>
        {data && data.length &&
          <Grid sx={{display: {xs: "none", md: "flex"}, padding: "25px 0"}} container spacing={2}>
            {/*<Grid xs={1}>*/}
            {/*  <Checkbox />*/}
            {/*</Grid>*/}
            <Grid xs={2}>
              <strong>
                Изображение
              </strong>
            </Grid>
            <Grid xs={2}>
              <strong>
                Состояние
              </strong>
            </Grid>
            <Grid xs={2}>
              <strong>
                Цвет
              </strong>
            </Grid>
            <Grid xs={3}>
              <strong>
                Описание
              </strong>
            </Grid>
            <Grid xs={3}>
              <strong>
                Информация
              </strong>
            </Grid>
          </Grid>
        }
        {data}
      </Box>
      {items &&
      <Pagination urlBase="catalog" itemsLen={items.length} productsOnPage={productsOnPage} setProductsOnPage={setProductsOnPage}/>
      }
    </div>
  );
}
